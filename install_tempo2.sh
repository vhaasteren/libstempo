#!/bin/bash -e

# get install location
if [ $# -eq 0 ]
	then
		echo 'No install location defined, using' $HOME'/.local/'
		prefix=$HOME/.local/
	else
		prefix=$1
		echo 'Will install in' $prefix
fi

# make a destination directory for runtime files
export TEMPO2=$prefix/share/tempo2
mkdir -p $TEMPO2

curl -O https://bitbucket.org/psrsoft/tempo2/get/2021.07.1-correct.tar.gz
tar zxvf 2021.07.1-correct.tar.gz

cd psrsoft-tempo2-*

# remove LT_LIB_DLLOAD from configure.ac
if [[ "$(uname -s)" == "Darwin" ]]; then
  sed -i '' "s/LT_LIB_DLLOAD//g" "configure.ac"
else
  sed -i "s/LT_LIB_DLLOAD//g" "configure.ac"
fi

./bootstrap
# Prevent autoconf from enabling C23 (where bool is a keyword),
# which breaks tempo2's jpleph.c `typedef int bool;`
./configure --prefix=$prefix ac_cv_prog_cc_c23=no
make
make install
cp -r T2runtime/* $TEMPO2
cd ..

rm -rf psrsoft-tempo2-*
rm -rf 2021.07.1-correct.tar.gz
echo "Set TEMPO2 environment variable to ${TEMPO2} to make things run more smoothly."
