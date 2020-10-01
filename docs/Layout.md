# Layout of the ioda-converters repository

## Rationale

ioda-converters is a repository that contains a bunch of converter utilities. We do not intend to
split them up.

## Repository source directory

```
ioda-converters
 │
 ├──── CMakeLists.txt [Build system]
 │
 ├──── README.md [Project readme file used by GitHub and Doxygen]
 │
 ├──── CI [Travis / AWS Codebuild scripts]
 │
 ├──── cmake [CMake include files]
 │
 ├──── docs [Markdown and rst documentation]
 │
 ├──── include [Public header files that get included by downstream targets. Binary module files are not here.]
 │      │
 │      ├──── cpp [each language's headers should remain distinct]
 │      │      │
 │      │      └──── lib_BufrParser
 │      │             │
 │      │             └──── BufrParser [Public headers for Ron's BUFR-parsing library]
 │      │                    │
 │      │                    └──── [Public C++ header files]
 │      │
 │      └──── fortran [usually not present, as Fortran exports compiler-specific module files]
 │             │
 │             └──── ioda-converters-lib-2
 │                    │
 │                    └──── [Public Fortran files]
 │
 ├──── info [deprecated. Currently contains two text examples. Remove.]
 │
 ├──── src [Source code and private header files. Each converter gets its own directory.]
 │      │
 │      ├──── CMakeLists.txt [add_subdirectory calls. Libraries first, then the other targets.]
 │      │
 │      ├──── lib_BufrParser [Ron's BUFR-parsing code]
 │      │
 │      ├──── lib_python [Convenience functions in Python for writing a converter]
 │      │
 │      ├──── chem
 │      │
 │      ├──── gnssro
 │      │
 │      └──── [others]
 │ 
 ├──── test
 │      │
 │      ├──── CMakeLists.txt [add_subdirectory calls]
 │      │
 │      └──── [tests for each converter]
 │
 └──── tools
        │
        ├──── iodaconv_cpplint.py [deprecated. Only the configuration file should be kept.
        │                          The general script should be in jedicmake.]
        │
        └──── [shell scripts and other stuff]

````

## Repository build directory

## Repository install directory

