#!/bin/bash

# NOTE that some of the releases named in this might be old and links may be broken. As is it will run when available packages are downloaded with apt, but not necessarily if building all packages from source.

app_dir=$HOME/ffmpeg
source_dir=$app_dir/src
build_dir=$app_dir/build
bin_dir=$app_dir/bin

install_dir=/usr/local
bin_install_dir=$install_dir/bin
lib_install_dir=$install_dir/lib

ldconf_name="$USER"_ffmpeg.conf
nprocs=4

confirm () {
    # call with a prompt string or use a default
    read -r -p "${1:-Are you sure you want to do this? [y/N]} " response
    case $response in
        [yY][eE][sS]|[yY])
            true
            ;;
        *)
            false
            ;;
    esac
}

make_dir () {
    if [ ! -d $1 ]; then mkdir -p $1; fi
}

# NOTE: This is not necessary if bin_dir is $HOME/bin (see $HOME/.profile)
set_path () {
    # add bin_dir to $USER's $PATH
    if [ "$PATH" != *"$bin_dir"* ]; then  echo "export PATH=$bin_dir:\$PATH" >> $HOME/.bashrc; fi

}

install_binaries () {
    sudo ln -sf $bin_dir/* $bin_install_dir
    #if [ ! -e "$ldconf_name" ]; then sudo sh -c "echo $lib_dir > /etc/ld.so.conf.d/$ldconf_name"; fi
}

remove_binaries () {
    for f in `ls $bin_dir`; do sudo rm $bin_install_dir/$f; done
}

remove_libraries () {
    for f in `ls $build_dir/lib/`; do sudo rm $lib_install_dir/$f; done
}

configure_linker () {
    sudo ln -sf $build_dir/lib/* $lib_install_dir
    #if [ ! -e "$ldconf_name" ]; then sudo sh -c "echo $lib_dir > /etc/ld.so.conf.d/$ldconf_name"; fi
    sudo ldconfig
    echo "Linker configuration complete. You may need to restart your session (by logging out and in again) for this to take effect."
}

install_depends () {
    # update sources and install dependency packages
    sudo apt-get update
    sudo apt-get -y --force-yes install autoconf automake build-essential libass-dev libfreetype6-dev libsdl1.2-dev libtheora-dev libtool libva-dev libvdpau-dev libvorbis-dev libxcb1-dev libxcb-shm0-dev libxcb-xfixes0-dev pkg-config texinfo zlib1g-dev libxvidcore4 libxvidcore-dev  # yasm libx264-dev libmp3lame-dev libopus-dev
}

install_yasm () {
    if [ "$1" == "" ]; then
        sudo apt-get -y install yasm
    elif [ "$1" == "--build" ]; then
        cd $source_dir
        wget http://www.tortall.net/projects/yasm/releases/yasm-1.3.0.tar.gz
        tar xzvf yasm-1.3.0.tar.gz
        cd yasm-1.3.0
        ./configure --prefix="$build_dir" --bindir="$bin_dir"
        make -j $nprocs
        make install
        make distclean
    fi
}

install_x264 () {
    if [ "$1" == "" ]; then
        sudo apt-get -y install libx264-dev
    elif [ "$1" == "--build" ]; then
        cd $source_dir
        wget http://download.videolan.org/pub/x264/snapshots/last_x264.tar.bz2
        tar xjvf last_x264.tar.bz2
        cd x264-snapshot*
        PATH="$bin_dir:$PATH" ./configure --prefix="$build_dir" --bindir="$bin_dir" --enable-shared
        PATH="$bin_dir:$PATH" make -j $nprocs
        make install
        make distcleanf
    fi
}

install_libfdk () {
    # libfdk-aac
    sudo apt-get -y install unzip
    cd $source_dir
    wget -O fdk-aac.zip https://github.com/mstorsjo/fdk-aac/zipball/master
    unzip fdk-aac.zip
    cd mstorsjo-fdk-aac*
    autoreconf -fiv
    ./configure --prefix="$build_dir" --enable-shared
    make -j $nprocs
    make install
    make distclean
}

install_libmp3lame () {
    if [ "$1" == "" ]; then
        sudo apt-get -y install libmp3lame-dev
    elif [ "$1" == "--build" ]; then
        cd $source_dir
        sudo apt-get -y install nasm
        cd $source_dir
        wget http://downloads.sourceforge.net/project/lame/lame/3.99/lame-3.99.5.tar.gz
        tar xzvf lame-3.99.5.tar.gz
        cd lame-3.99.5
        ./configure --prefix="$build_dir" --enable-nasm --enable-shared
        make -j $nprocs
        make install
        make distclean
    fi
}

install_libopus () {
    if [ "$1" == "" ]; then
        sudo apt-get -y install libopus-dev
    elif [ "$1" == "--build" ]; then
        cd $source_dir
        wget http://downloads.xiph.org/releases/opus/opus-1.1.tar.gz
        tar xzvf opus-1.1.tar.gz
        cd opus-1.1
        ./configure --prefix="$build_dir" --enable-shared
        make -j $nprocs
        make install
        make distclean
    fi
}

install_libvpx () {
    # libvpx
    latestRelease=v1.7.0
    latestPackage=$latestRelease.tar.gz
    cd $source_dir
    wget -O libvpx-$latestPackage https://chromium.googlesource.com/webm/libvpx/+archive/$latestPackage
    mkdir libvpx-$latestRelease
    cd libvpx-$latestRelease
    tar zxvf ../libvpx-$latestPackage
    PATH="$bin_dir:$PATH" ./configure --prefix="$build_dir" --disable-examples --enable-shared
    PATH="$bin_dir:$PATH" make -j $nprocs
    make install
    make clean
}

install_ffmpeg () {
    # ffmpeg
    cd $source_dir
    wget http://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2
    tar xjvf ffmpeg-snapshot.tar.bz2
    cd ffmpeg
    PATH="$bin_dir:$PATH" PKG_CONFIG_PATH="$build_dir/lib/pkgconfig" ./configure \
    --prefix="$build_dir" \
    --extra-cflags="-I$build_dir/include" \
    --extra-ldflags="-L$build_dir/lib" \
    --bindir="$bin_dir" \
    --enable-gpl \
    --enable-libass \
    --enable-libfdk-aac \
    --enable-libfreetype \
    --enable-libmp3lame \
    --enable-libopus \
    --enable-libtheora \
    --enable-libvorbis \
    --enable-libvpx \
    --enable-libx264 \
    --enable-libxvid \
    --enable-nonfree \
    --enable-shared
    PATH="$bin_dir:$PATH" make -j $nprocs
    make install
    make distclean
    hash -r
}

install_full_ffmpeg () {
    if ! (make_dir $source_dir && make_dir $build_dir && make_dir $bin_dir && make_dir $lib_dir); then
        echo "\n ### Error! Could not create one of the directories:\n\t$source_dir\n\t$build_dir\n\t$bin_dir\n\t$lib_dir\n\t\t\t\t ###\n"
        exit 1
    fi
    if ! install_depends; then
        echo "\n ### Error! Could not install dependencies! See above for details! ###\n"
        exit 1
    fi
    if ! install_yasm; then
        echo "\n ### Error! Could not install yasm! See above for details! See above for details! ###\n"
        exit 1
    fi
    if ! install_x264; then
        echo -e "\n ### Error! Could not install x264 libraries! See above for details! ###\n"
        exit 1
    fi
    if ! install_libfdk; then
        echo "\n ### Error! Could not install libfdk-aac! See above for details! ###\n"
        exit 1
    fi
    if ! install_libmp3lame; then
        echo "\n ### Error! Could not install libmp3lame! See above for details! ###\n"
        exit 1
    fi
    if ! install_libopus; then
        echo "\n ### Error! Could not install libopus! See above for details! ###\n"
        exit 1
    fi
    if ! install_libvpx; then
        echo "\n ### Error! Could not install libvpx! See above for details! ###\n"
        exit 1
    fi
    if ! install_ffmpeg; then
        echo "\n ### Error! Could not install ffmpeg! See above for details! ###\n"
        exit 1
    fi
}

# ### Entry Point ###
# record start time
START_TIME=$(date +%s)

# check for existing installations
if [ -e "$bin_dir/ffmpeg" ]
then
    echo "Existing ffmpeg installation found!"

    if [ "$1" == "--upgrade" ] || [ "$1" == "-u" ]; then
        echo "Received upgrade directive! Continuing without confirmation!"
        echo "Upgrading ffmpeg now!"
        sudo rm -r $bin_dir $lib_dir $build_dir $source_dir
        if ! (install_full_ffmpeg && configure_linker)
        then
            echo "Upgrade failed! See above for details!"
            exit 1
        fi
        
    elif [ "$1" == "--remove" ] || [ "$1" == "--uninstall" ]; then
        echo "Received command to REMOVE exsiting ffmpeg installation!"
        if confirm
        then
            echo "Removing ffmpeg binaries and libraries now!"
            remove_binaries
            remove_libraries
            sudo rm -r $bin_dir $lib_dir
        else
            echo "Finishing..."
        fi
    elif [ "$1" == "--purge" ]; then
        echo "Received command to PURGE ALL FILES FOR INSTALLED FFMPEG AND DEPENDENCIES!"
        if confirm
        then
            echo "Removing ALL FFMPEG-RELATED FILES now!"
            remove_binaries
            remove_libraries
            sudo rm -r $bin_dir $lib_dir $build_dir $source_dir
        else
            echo "Finishing..."
        fi
    elif [ "$1" == "-n" ]; then
        echo "Finishing..."
    else
        echo "No directives supplied. Would you like to upgrade the existing ffmpeg?"
        if confirm; then
            echo "Upgrading ffmpeg now!"
            echo "Deleting existing files!"
            sudo rm -r $bin_dir $lib_dir $build_dir $source_dir
            echo "Beginning instalation!"
            if ! (install_full_ffmpeg && configure_linker); then
                echo "Upgrade failed! See above for details!"
                exit 1
            fi
        else
            echo "Finishing..."
        fi
    fi
else
    echo "No existing ffmpeg was found. Installing it now!"
    if ! (install_full_ffmpeg && install_binaries && configure_linker); then
        echo "Installation failed! See above for details!"
    else
        echo "MANPATH_MAP $bin_dir $build_dir/share/man" >> ~/.manpath
        echo "Installation complete! Run "source ~/.profile" or restart your session to add the necessary information to your PATH environment variables."
        END_TIME=$(date +%s)
        secs=$(($END_TIME-$START_TIME))
        echo -e "\n\tInstallation completed in $secs seconds!"
    fi
fi

