# CMake generated Testfile for 
# Source directory: /scratch2/NCEPDEV/marineda/Youlong.Xia/save/ioda-converters/src/marine
# Build directory: /scratch2/NCEPDEV/marineda/Youlong.Xia/save/ioda-converters/bulid1/src/marine
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
add_test(iodaconv_marine_coding_norms "/scratch2/NCEPDEV/marineda/Youlong.Xia/save/ioda-converters/bulid1/bin/iodaconv_lint.sh" "/scratch2/NCEPDEV/marineda/Youlong.Xia/save/ioda-converters/src/marine" "/scratch2/NCEPDEV/marineda/Youlong.Xia/save/ioda-converters")
set_tests_properties(iodaconv_marine_coding_norms PROPERTIES  ENVIRONMENT "OMP_NUM_THREADS=1" LABELS "iodaconv;script" _BACKTRACE_TRIPLES "/scratch1/NCEPDEV/jcsda/Ryan.Honeyager/jedi/usr/local/intel-18.0.5.274/impi-2018.0.4/netcdf-hdf5parallel-4.7.0/share/ecbuild/cmake/ecbuild_add_test.cmake;406;add_test;/scratch2/NCEPDEV/marineda/Youlong.Xia/save/ioda-converters/src/marine/CMakeLists.txt;42;ecbuild_add_test;/scratch2/NCEPDEV/marineda/Youlong.Xia/save/ioda-converters/src/marine/CMakeLists.txt;0;")
