#!/bin/bash

# Move to the external folder
cd ${0%/*}

# Download ACADOS if needed
if [ ! -f acados/CMakeLists.txt ]; then
  echo "Git submodules not initialized. Initializing"
  git submodule update --recursive --init
fi

# Check if everything required by the script is present
echo "Processing arguments"
echo ""

# Check if there are a number of CPUs for Acados multiprocessing
ARG1=${1:NB_CPU}
if [ -z "$ARG1" ]; then
  $ARG1=$CPU_COUNT
  echo "  Argument 1 (NB_CPU) not provided, falling back on maximum number of CPUs ($ARG1)."
  echo ""
fi

if [ "$1" ]; then
	echo "  Number of threads for acados with openMP asked : NB_CPU=$1"
	echo ""
fi

ARG2=${2:-$CONDA_PREFIX}
if [ -z "$ARG2" ]; then
  echo "  Argument 2 (CMAKE_INSTALL_PREFIX) is missing and you are not using conda."
  echo "  Please provide a path for installation"
  exit 1
fi

if [ -z "$1" ]; then
  echo "  Argument 2 (CMAKE_INSTALL_PREFIX) not provided, falling back on CONDA_PREFIX"
  echo "  CONDA_PREFIX=$CONDA_PREFIX"
  echo ""
fi

ARG3=${3:-X64_AUTOMATIC}
if [ -z "$3" ]; then
  echo "  Argument 3 (BLASFEO_TARGET) not provided, falling back on X64_AUTOMATIC"
  echo ""
fi

# Move to the build folder
echo "Compiling ACADOS"
echo ""
rm -rf acados/build/
mkdir acados/build
cd acados/build

# Run cmake
cmake . .. \
  -DACADOS_INSTALL_DIR="$ARG2"\
  -DACADOS_PYTHON=ON\
  -DACADOS_WITH_QPOASES=ON\
  -DACADOS_WITH_OSQP=ON\
  -DBLASFEO_TARGET="$ARG3"\
  -DCMAKE_INSTALL_PREFIX="$ARG2"\
  -DACADOS_WITH_OPENMP=ON\
  -DACADOS_NUM_THREADS="$ARG1"
make install -j$CPU_COUNT



# Prepare the Python interface
cd ../interfaces/acados_template

# Use gnu-sed instead of osx native sed
if [ "$CONDA_PREFIX" ]; then
  conda install sed wget git cmake -cconda-forge -y
fi

# Prepare some modification on the files so it works with biorbd
# Allow for any python
TO_REPLACE_PYTHON_REQUIRED="python_requires"
REPLACE_PYTHON_REQUIRED_BY="# python_requires"

# Removing the casadi dependency (already installed from biorbd)
TO_REPLACE_CASADI_DEP="'casadi"
REPLACE_CASADI_DEP_BY="# 'casadi"

# Add the simulink file
TO_REPLACE_JSON_DEP="'acados_sim_layout.json',"
REPLACE_JSON_DEP_BY="'acados_sim_layout.json',\n       'simulink_default_opts.json',"

# Modify relative path of acados_template is install doesn't have the 
# same structure as the source folder
TO_REPLACE_PATH="'..\/..\/..\/'"
REPLACE_PATH_BY="'..\/..\/..\/..\/'"

# Change acados path
TO_REPLACE_ACADOS_SOURCE="    ACADOS_PATH = os.environ.get('ACADOS_SOURCE_DIR')"
REPLACE_ACADOS_SOURCE_BY="    ACADOS_PATH = os.environ['CONDA_PREFIX']"

TO_REPLACE_ACADOS_PYTHON="ACADOS_PYTHON_INTERFACE_PATH = os.environ.get('ACADOS_PYTHON_INTERFACE_PATH')"
REPLACE_ACADOS_PYTHON_BY="import site\n    acados_path = site.getsitepackages()\n    ACADOS_PYTHON_INTERFACE_PATH = os.path.join(acados_path[0], 'acados_template')"

# Change acados external library linking at run time
TO_REPLACE_LIB_PATH="libacados_ocp_solver_name = f'{lib_prefix}acados_ocp_solver_{self.model_name}{lib_ext}'"
REPLACE_LIB_PATH_BY="libacados_ocp_solver_name = f'{lib_prefix}acados_ocp_solver_{self.model_name}{lib_ext}'\n        self.shared_lib_name = os.path.join(code_export_directory, libacados_ocp_solver_name)\n        import site\n        acados_path = site.getsitepackages()\n        libacados_ocp_solver_name = f'{lib_prefix}acados_ocp_solver_{self.model_name}{lib_ext}'\n        # Relink macos lib\n        acados_ext_lib_path = os.path.abspath(acados_path[0]+'\/..\/..')\n        os.system(\n            f'install_name_tool -change libhpipm.dylib {acados_ext_lib_path}\/libhpipm.dylib {self.shared_lib_name}')\n        os.system(\n            f'install_name_tool -change libblasfeo.dylib {acados_ext_lib_path}\/libblasfeo.dylib {self.shared_lib_name}')"
# Perform the modifications
sed -i "s/$TO_REPLACE_PYTHON_REQUIRED/$REPLACE_PYTHON_REQUIRED_BY/" setup.py
sed -i "s/$TO_REPLACE_CASADI_DEP/$REPLACE_CASADI_DEP_BY/" setup.py
sed -i "s/$TO_REPLACE_JSON_DEP/$REPLACE_JSON_DEP_BY/" setup.py
sed -i "s/$TO_REPLACE_PATH/$REPLACE_PATH_BY/" acados_template/utils.py
sed -i "s/$TO_REPLACE_ACADOS_PYTHON/$REPLACE_ACADOS_PYTHON_BY/" acados_template/utils.py
sed -i "s/$TO_REPLACE_ACADOS_SOURCE/$REPLACE_ACADOS_SOURCE_BY/" acados_template/utils.py
sed -i "s/$TO_REPLACE_LIB_PATH/$REPLACE_LIB_PATH_BY/" acados_template/acados_ocp_solver.py

# Change acados external lib linking permanently
install_name_tool -change libqpOASES_e.3.1.dylib $CONDA_PREFIX/lib/libqpOASES_e.3.1.dylib $CONDA_PREFIX/lib/libacados.dylib
install_name_tool -change libhpipm.dylib $CONDA_PREFIX/lib/libhpipm.dylib $CONDA_PREFIX/lib/libacados.dylib
install_name_tool -change libblasfeo.dylib $CONDA_PREFIX/lib/libblasfeo.dylib $CONDA_PREFIX/lib/libacados.dylib
install_name_tool -change libblasfeo.dylib $CONDA_PREFIX/lib/libblasfeo.dylib $CONDA_PREFIX/lib/libhpipm.dylib

# Install the Python interface
pip install .
cd ../..

# Automatically download Tera 
TERA_INSTALL_SCRIPT=$(pwd)/ci/osx/install_t_renderer.sh
pushd $ARG2;
  chmod +x $TERA_INSTALL_SCRIPT;
  $TERA_INSTALL_SCRIPT;
popd;

# Undo the modifications to the files (so it is not picked up by Git)
git reset --hard


