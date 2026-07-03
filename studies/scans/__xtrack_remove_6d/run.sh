#!/bin/bash
export PYTHONNOUSERSITE=1
unset PYTHONPATH
unset CONDA_PYTHON_EXE
unset LD_LIBRARY_PATH
unset SHLIB_PATH
unset CMAKE_INCLUDE_PATH
unset SRM_PATH
unset MODULES_RUN_QUARANTINE
unset MANPATH
export PATH=/usr/bin:/bin
mkdir my_env
tar -xvzf DA19.tar.gz -C my_env
source my_env/bin/activate
echo "Using Python: $(which python)"
echo $PYTHONPATH
unset PYTHONPATH
echo $PYTHONPATH
echo "Files: $(ls)"
for f in *.zip; do
  echo "Unzipping $f"
  unzip "$f"
done
mkdir xtrack_0007
cp -f config.yaml xtrack_0007/config.yaml
cp -f *.py xtrack_0007
cp -f *.log xtrack_0007
cp -f *.json xtrack_0007
cp -f config_gen1.yaml config.yaml
cd xtrack_0007
../my_env/bin/python 2_configure_and_track.py > output_python.txt 2> error_python.txt
rm -f ../config.yaml
mv config.yaml config_final.yaml
cp -rf * ../
cd ..
echo "Files in final output location:" 
ls
