"""
A very simple yet meaningful optimal control program consisting in a pendulum starting downward and ending upward
while requiring the minimum of generalized forces. The solver is only allowed to move the pendulum sideways.

This simple example is a good place to start investigating explicit and implicit dynamics. There are extra controls in
implicit dynamics which are joint acceleration qddot thus, u=[tau, qddot]^T. Also a dynamic constraints is enforced at
each shooting nodes such that inverse_dynamics(q,qdot,qddot) - tau = 0.

Finally, once it finished optimizing, it animates the model using the optimal solution.
"""

import biorbd_casadi as biorbd
from bioptim import (
    BiorbdModel,
    OptimalControlProgram,
    DynamicsFcn,
    Dynamics,
    Bounds,
    InitialGuess,
    ObjectiveFcn,
    OdeSolver,
    CostType,
    Solver,
    BoundsList,
    ObjectiveList,
    RigidBodyDynamics,
    Solution,
)
import matplotlib.pyplot as plt
import numpy as np


def prepare_ocp(
    biorbd_model_path: str,
    final_time: float,
    n_shooting: int,
    ode_solver: OdeSolver = OdeSolver.RK1(n_integration_steps=1),
    use_sx: bool = False,
    n_threads: int = 1,
    rigidbody_dynamics: RigidBodyDynamics = RigidBodyDynamics.ODE,
) -> OptimalControlProgram:
    """
    The initialization of an ocp

    Parameters
    ----------
    biorbd_model_path: str
        The path to the biorbd model
    final_time: float
        The time in second required to perform the task
    n_shooting: int
        The number of shooting points to define int the direct multiple shooting program
    ode_solver: OdeSolver = OdeSolver.RK4()
        Which type of OdeSolver to use
    use_sx: bool
        If the SX variable should be used instead of MX (can be extensive on RAM)
    n_threads: int
        The number of threads to use in the paralleling (1 = no parallel computing)
    rigidbody_dynamics: RigidBodyDynamics
        rigidbody dynamics ODE or DAE
    Returns
    -------
    The OptimalControlProgram ready to be solved
    """

    bio_model = BiorbdModel(biorbd_model_path)

    objective_functions = ObjectiveList()
    objective_functions.add(ObjectiveFcn.Lagrange.MINIMIZE_CONTROL, key="tau")

    # Dynamics
    dynamics = Dynamics(DynamicsFcn.TORQUE_DRIVEN, rigidbody_dynamics=rigidbody_dynamics)

    # Path constraint
    tau_min, tau_max, tau_init = -100, 100, 0

    # Be careful to let the accelerations not to much bounded to find the same solution in implicit dynamics
    if (
        rigidbody_dynamics == RigidBodyDynamics.DAE_INVERSE_DYNAMICS
        or rigidbody_dynamics == RigidBodyDynamics.DAE_FORWARD_DYNAMICS
    ):
        qddot_min, qddot_max, qddot_init = -1000, 1000, 0

    x_bounds = BoundsList()
    x_bounds.add(bounds=bio_model.bounds_from_ranges(["q", "qdot"]))
    x_bounds[0][:, [0, -1]] = 0
    x_bounds[0][1, -1] = 3.14

    # Initial guess
    n_q = bio_model.nb_q
    n_qdot = bio_model.nb_qdot
    n_qddot = bio_model.nb_qddot
    n_tau = bio_model.nb_tau
    x_init = InitialGuess([0] * (n_q + n_qdot))

    # Define control path constraint
    # There are extra controls in implicit dynamics which are joint acceleration qddot.
    if (
        rigidbody_dynamics == RigidBodyDynamics.DAE_INVERSE_DYNAMICS
        or rigidbody_dynamics == RigidBodyDynamics.DAE_FORWARD_DYNAMICS
    ):
        u_bounds = Bounds([tau_min] * n_tau + [qddot_min] * n_qddot, [tau_max] * n_tau + [qddot_max] * n_qddot)
    else:
        u_bounds = Bounds([tau_min] * n_tau, [tau_max] * n_tau)

    u_bounds[1, :] = 0  # Prevent the model from actively rotate

    if (
        rigidbody_dynamics == RigidBodyDynamics.DAE_INVERSE_DYNAMICS
        or rigidbody_dynamics == RigidBodyDynamics.DAE_FORWARD_DYNAMICS
    ):
        u_init = InitialGuess([0] * (n_tau + n_qddot))
    else:
        u_init = InitialGuess([0] * n_tau)

    return OptimalControlProgram(
        bio_model,
        dynamics,
        n_shooting,
        final_time,
        x_init=x_init,
        u_init=u_init,
        x_bounds=x_bounds,
        u_bounds=u_bounds,
        objective_functions=objective_functions,
        ode_solver=ode_solver,
        use_sx=use_sx,
        n_threads=n_threads,
    )


def solve_ocp(
    rigidbody_dynamics: RigidBodyDynamics, max_iter: int = 10000, model_path: str = "models/pendulum.bioMod"
) -> Solution:
    """
    The initialization of ocp with implicit_dynamics as the only argument

    Parameters
    ----------
    rigidbody_dynamics: RigidBodyDynamics
        rigidbody dynamics DAE or ODE
    max_iter: int
        maximum iterations of the solver
    model_path: str
        The path to the biorbd model
    Returns
    -------
    The OptimalControlProgram ready to be solved
    """
    n_shooting = 200  # The higher it is, the closer implicit and explicit solutions are.
    ode_solver = OdeSolver.RK2(n_integration_steps=1)
    time = 1

    # --- Prepare the ocp with implicit dynamics --- #
    ocp = prepare_ocp(
        biorbd_model_path=model_path,
        final_time=time,
        n_shooting=n_shooting,
        ode_solver=ode_solver,
        rigidbody_dynamics=rigidbody_dynamics,
    )

    # --- Custom Plots --- #
    ocp.add_plot_penalty(CostType.ALL)

    # --- Solve the ocp --- #
    sol_opt = Solver.IPOPT(show_online_optim=False)
    sol_opt.set_maximum_iterations(max_iter)
    sol = ocp.solve(sol_opt)

    return sol


def prepare_plots(sol_implicit, sol_semi_explicit, sol_explicit):
    plt.figure()
    tau_ex = sol_explicit.controls["tau"][0, :]
    tau_sex = sol_semi_explicit.controls["tau"][0, :]
    tau_im = sol_implicit.controls["tau"][0, :]
    plt.plot(tau_ex, label="tau in explicit dynamics")
    plt.plot(tau_sex, label="tau in semi-explicit dynamics")
    plt.plot(tau_im, label="tau in implicit dynamics")
    plt.xlabel("frames")
    plt.ylabel("Torque (Nm)")
    plt.legend()

    lalbels = ["explicit", "semi-explicit", "implicit"]

    plt.figure()
    cost_ex = np.sum(sol_explicit.cost)
    cost_sex = np.sum(sol_semi_explicit.cost)
    cost_im = np.sum(sol_implicit.cost)
    plt.bar([0, 1, 2], width=0.3, height=[cost_ex, cost_sex, cost_im])
    plt.xticks([0, 1, 2], lalbels)
    plt.ylabel("weighted cost function")

    plt.figure()
    time_ex = np.sum(sol_explicit.real_time_to_optimize)
    time_sex = np.sum(sol_semi_explicit.real_time_to_optimize)
    time_im = np.sum(sol_implicit.real_time_to_optimize)
    plt.bar([0, 1, 2], width=0.3, height=[time_ex, time_sex, time_im])
    plt.xticks([0, 1, 2], lalbels)
    plt.ylabel("time (s)")

    plt.show()


def main():
    """
    The pendulum runs two ocp with implicit and explicit dynamics and plot comparison for the results
    """

    # --- Prepare the ocp with implicit and explicit dynamics --- #
    sol_implicit = solve_ocp(rigidbody_dynamics=RigidBodyDynamics.DAE_INVERSE_DYNAMICS)
    sol_semi_explicit = solve_ocp(rigidbody_dynamics=RigidBodyDynamics.DAE_FORWARD_DYNAMICS)
    sol_explicit = solve_ocp(rigidbody_dynamics=RigidBodyDynamics.ODE)

    # --- Show the results in a bioviz animation --- #
    sol_implicit.print_cost()
    # sol_implicit.animate(n_frames=100)
    # sol_implicit.graphs()

    # --- Show the results in a bioviz animation --- #
    sol_semi_explicit.print_cost()
    # sol_semi_explicit.animate(n_frames=100)
    # sol_semi_explicit.graphs()

    # --- Show the results in a bioviz animation --- #
    sol_explicit.print_cost()
    # sol_explicit.animate(n_frames=100)
    # sol_explicit.graphs()

    # Tau are closer between implicit and explicit when the dynamic is more discretized,
    # meaning the more n_shooting is high, the more tau are close.
    prepare_plots(sol_implicit, sol_semi_explicit, sol_explicit)


if __name__ == "__main__":
    main()
