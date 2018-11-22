#!/usr/bin/env python
'''
This script is used to build PATrace under different platforms.
To use this script, please create a empty directory and run it with the path to the root source directory of the content_capturing.
The script will create two directories, 'build' and 'install'.
The new-created directory 'build' is the place all 'cmake' & 'make' commands happen.
While the directory 'install' is used to store all built binary files. The structure of 'install' directory is like the following:
    patrace
    ----fbdev
    --------debug
    ------------bin
    ------------log.txt
    --------release
    ------------bin
    ------------log.txt
    ----x11_x64
    --------debug
    ------------bin
    ------------tools
    ------------python_tools
    ------------log.txt
    --------release
    ------------bin
    ------------tools
    ------------python_tools
    ------------log.txt
    ----x11_x32
    --------debug
    ------------bin
    ------------log.txt
    --------release
    ------------bin
    ------------log.txt
    ----android
    --------release
    ------------egltrace
    ------------eglretrace
    ------------fakedriver
    ------------log.txt
    ----udriver_x64
    --------debug
    ------------bin
    ------------log.txt
    --------release
    ------------bin
    ------------log.txt

If you get any errors during the compilation, you will get some error messages in the shell. You could refer to the log files under the install directory for more details.
'''

import sys
import os
import re
import shutil
import subprocess
import shlex
from optparse import OptionParser

HEADER = '\033[37m'
OKBLUE = '\033[34m'
OKGREEN = '\033[32m'
WARNING = '\033[93m'
WARNRED = '\033[31m'
ENDC = '\033[0m'

ANDROID_TARGET = 'android-23'

SUCCESS = 0
ERROR = 1

linux_platforms = [
    'x11_x32',
    'x11_x64',
    'udriver_x64',
    'fbdev_arm',
    'fbdev_arm_hardfloat',
    'fbdev_aarch64',
    'fbdev_x32',
    'fbdev_x64',
    'wayland_arm_hardfloat',
    'wayland_aarch64',
    'wayland_x64',
    'rhe6_x32',
    'rhe6_x64',
]

all_platforms = linux_platforms + [
    #'win',
    'android',
]


def get_patrace_cmake_path(src_path):
    return os.path.abspath(os.path.join(src_path, 'patrace', 'project', 'cmake'))


def cmake_dict(src_path):
    cmake_file = os.path.join(get_patrace_cmake_path(src_path), 'CMakeLists.txt')

    # Parse CMakeLists.txt
    with open(cmake_file) as f:
        set_lines = [tuple(line[:-2].split('(')[1].split(')')[0].split(' '))
                     for line in f
                     if line[:3].lower() == 'set']

    return dict([set_line for set_line in set_lines if len(set_line) == 2])


def update_android_versions(major, minor, patch, revision, version_type, source_root, android_target_dir, **kw):
    # Generate version string
    release_version = 'r{major}p{minor_patch} {revision} {version_type}'.format(
        major=major,
        minor_patch=("{}.{}".format(minor, patch) if patch else minor),
        revision=revision,
        version_type=version_type
    )

    release_code = str(int('%d%02d%d' % (major, minor, patch)))

    # Write correct version in <string name="version"></string>
    in_file = os.path.join(android_target_dir, 'res/values/.strings.xml.template')
    out_file = os.path.join(android_target_dir, 'res/values/strings.xml')
    try:
        shutil.copy(in_file, out_file)
    except IOError:
        pass
    release_version_command = r'sed -i -e "s/\(<string name=\"version\">\).*\(<\/string>\)/\1{release_version}\2/g" {edit_file}'.format(
        release_version=release_version,
        edit_file=out_file
    )
    run_command(release_version_command)

    # Write correct release code in android:versionCode=""
    in_file = os.path.join(android_target_dir, '.AndroidManifest.xml.template')
    out_file = os.path.join(android_target_dir, 'AndroidManifest.xml')
    try:
        shutil.copy(in_file, out_file)
    except IOError:
        pass
    release_code_pattern = r'sed -i -e "s/\(android:versionCode=\"\)[0-9]*/\1{release_code}/g" {edit_file}'.format(
        release_code=release_code,
        edit_file=out_file
    )
    run_command(release_code_pattern)


def update_cmake_versions(major, minor, patch, revision, version_type, source_root, cmake_script, **kw):
    run_command(
        (
            'cmake'
            ' -DSRC_ROOT={source_root}'
            ' -DPATRACE_VERSION_MAJOR={major}'
            ' -DPATRACE_VERSION_MINOR={minor}'
            ' -DPATRACE_VERSION_PATCH={patch}'
            ' -DPATRACE_REVISION={revision}'
            ' -DPATRACE_VERSION_TYPE={version_type}'
            ' -DTEST_LIBRARY={testlib}'
            ' -DCMAKE_VERBOSE_MAKEFILE=TRUE'
            ' -P {cmake_script}'
        ).format(
            source_root=source_root,
            major=major,
            minor=minor,
            patch=patch,
            revision=revision,
            version_type=version_type,
            testlib=os.environ['TEST_LIBRARY'] if 'TEST_LIBRARY' in os.environ else '',
            cmake_script=cmake_script,
        )
    )


def print_info(string):
    print('')
    print(OKGREEN + string + ENDC)


def print_error(string):
    if string:
        print(WARNRED + 'From stderr : ' + string + ENDC)


def run_command(commandstr, log=sys.stdout, environment=None):
    print(OKBLUE + 'Command : ' + commandstr + ENDC)

    log.write('\n')
    log.write("Current directory : %s\n" % os.path.abspath(os.getcwd()))
    log.write('Command : ' + commandstr + '\n')
    log.write('\n')
    log.flush()

    command = shlex.split(commandstr)
    p = subprocess.Popen(command, stdout=log, stderr=log, env=environment)
    p.communicate()

    if p.returncode != SUCCESS:
        print "The following command failed with error code {code}:\n{command}".format(
            code=p.returncode,
            command=commandstr
        )
        sys.exit(p.returncode)

    return p.returncode


def check_log_erros(log_file):
    with open(log_file, 'r') as log:
        for line in log:
            if re.search(r"\berror\b", line) or re.search(r"\bError\b", line) \
                    or re.search(r"\bUnable to resolve\b", line) \
                    or re.search(r"\bundefined reference\b", line):
                print_error(line)


def build_project(platform, variant, build_dir, install_dir, project_path, log_file=sys.stdout, make_target='install', cmake_defines=[]):
    if platform == 'win':
        cmake_command = (
            'cmake'
            ' -H"{project_path}"'
            ' -DCMAKE_INSTALL_PREFIX:PATH="{install_dir}"'
            ' -B"{build_dir}"'
            ' -DENABLE_TOOLS=TRUE'
            ' -DCMAKE_SYSTEM_NAME=Windows'
            ' -DWINDOWSYSTEM=win'
            ' {other_params}'
        ).format(
            project_path=project_path,
            build_dir=build_dir,
            install_dir=install_dir,
            other_params="".join(["-D{} ".format(opt) for opt in cmake_defines]),
        )
    elif platform in ['rhe6_x32', 'rhe6_x64']:
        cmake_command = (
            'cmake'
            ' -H{project_path}'
            ' -DCMAKE_INSTALL_PREFIX:PATH={install_dir}'
            ' -DCMAKE_BUILD_TYPE={variant}'
            ' -DWINDOWSYSTEM=fbdev'
            ' -DENABLE_TOOLS=FALSE'
            ' -DENABLE_PYTHON_TOOLS=FALSE'
            ' -DARCH={arch}'
            ' -DCMAKE_VERBOSE_MAKEFILE=TRUE'
            ' -B{build_dir}'
            ' {other_params}'
        ).format(
            project_path=project_path,
            variant=variant.capitalize(),
            build_dir=build_dir,
            install_dir=install_dir,
            arch=platform.split('_')[1],
            other_params="".join(["-D{} ".format(opt) for opt in cmake_defines]),
        )
    else:
        cmake_command = (
            'cmake'
            ' -H{project_path}'
            ' -DCMAKE_TOOLCHAIN_FILE=toolchains/{toolchain}.cmake'
            ' -DCMAKE_INSTALL_PREFIX:PATH={install_dir}'
            ' -DCMAKE_BUILD_TYPE={variant}'
            ' -DTEST_LIBRARY={testlib}'
            ' -B{build_dir}'
            ' {other_params}'
        ).format(
            project_path=project_path,
            toolchain=platform,
            variant=variant.capitalize(),
            build_dir=build_dir,
            testlib=os.environ['TEST_LIBRARY'] if 'TEST_LIBRARY' in os.environ else '',
            install_dir=install_dir,
            other_params="".join(["-D{} ".format(opt) for opt in cmake_defines]),
        )

    if 'x32' in platform:
        cmake_command += ' -DCMAKE_C_FLAGS=-m32 -DCMAKE_CXX_FLAGS=-m32'

    if platform in ['fbdev_x32', 'fbdev_x64', 'rhe6_x32', 'rhe6_x64']:
        cmake_command += ' -DCMAKE_EXE_LINKER_FLAGS="-static-libgcc -static-libstdc++"'

    if not os.path.exists(build_dir):
        os.makedirs(build_dir)

    run_command(cmake_command, log_file)

    if platform == 'win':
        for project in ["eglretrace"]:
            make_command = (
                'devenv.com "{build_dir}\patrace.sln" /Build Release /Project eglretrace'
            ).format(
                build_dir=build_dir
            )
    else:
        make_command = (
            'make {target} -j8 -C "{build_dir}"'
        ).format(
            target=make_target,
            build_dir=build_dir,
        )

    run_command(make_command, log_file)


def install(src, dst):
    print "Installing: {src} -> {dst}".format(src=src, dst=dst)
    try:
        shutil.copy(src, dst)
    except IOError:
        print "Unable to copy file: {src}".format(src=src)
        sys.exit(ERROR)


def ndk_test():
    """Search for ndk-build idr. Return True if found otherwise False.

    If the NDK environment variable is set, then True is returned.

    If the NDK enviroment variable is NOT set, the ndk-build is searched for
    in all paths in PATH. If found, the NDK environment variable is set
    to the path where ndk-build was found.

    """

    if os.environ.get('NDK'):
        return True

    ndk_paths = [p
                 for p in os.environ["PATH"].split(os.pathsep)
                 if os.path.exists(os.path.join(p, 'ndk-build'))]

    if ndk_paths:
        os.environ['NDK'] = ndk_paths[0]
        return True

    return False


def update_android_projects(src_path):
    dirs_to_update = [p[0]
                      for p in os.walk(src_path)
                      if "AndroidManifest.xml" in p[2]]
    for path in dirs_to_update:
        name = os.path.basename(os.path.normpath(path))
        run_command(
            'android update project --name {name} --target {androidtarget} --path {path}'.format(
                name=name,
                androidtarget=ANDROID_TARGET,
                path=path,
            )
        )


def build_cmake(src_path, build_base_dir, install_base_dir):
    products = [
        {
            'name': 'patrace',
            'platforms': linux_platforms,
            'path': get_patrace_cmake_path(src_path),
        },
        {
            'name': 'fastforward',
            'platforms': linux_platforms,
            'path': get_patrace_cmake_path(src_path),
            'cmake_defines': ['FF_ONLY=1'],
        },
    ]

    variants = ('release', 'debug')

    for product in products:
        for platform in product['platforms']:
            for variant in variants:
                build_dir = os.path.join(product['name'], platform, variant)
                build_dir = os.path.join(build_base_dir, build_dir)

                install_dir = os.path.abspath(os.path.join(install_base_dir, product['name'], platform, variant))
                if not os.path.exists(install_dir):
                    os.makedirs(install_dir)

                log_file = os.path.join(install_dir, 'log.txt')

                # clear the content of the log
                if os.path.exists(log_file):
                    os.remove(log_file)

                with open(log_file, 'a') as log:
                    build_project(
                        platform=platform,
                        build_dir=build_dir.lower(),
                        install_dir=install_dir.lower(),
                        variant=variant,
                        project_path=product['path'],
                        log_file=log,
                        cmake_defines=product.get('cmake_defines', [])
                        #make_target='package',
                    )

                # open the log and check errors
                check_log_erros(log_file)


def build_android(src_path, product_names, install_base_dir=None):
    if not ndk_test():
        sys.stderr.write("""\
ndk-build not found.

Make sure it is in your path or that the NDK environment variable is
set and pointed to the directory where ndk-build resides."""
                         )
        return ERROR

    print "Using ndk-build: {0}".format(os.environ['NDK'])
    script_dir = os.path.dirname(os.path.realpath(__file__))

    products = {
        'patrace': {
            'name': 'patrace',
            'android_root': os.path.join(src_path, 'patrace', 'project', 'android'),
            'source_root': os.path.join(src_path, 'patrace', 'src'),
            'cmake_root': os.path.join(src_path, 'patrace', 'project', 'cmake'),
            'targets': [
                {
                    'name': 'egltrace',
                    'binaries': ('libs/armeabi-v7a/libinterceptor_patrace_arm.so',
                                 'libs/arm64-v8a/libinterceptor_patrace_arm64.so',
                                 'libs/x86/libinterceptor_patrace_x86.so', ),
                    'update-version-functions': [update_cmake_versions]
                },
                {
                    'name': 'fakedriver',
                    'binaries': (
                        'libs/armeabi-v7a/libEGL_wrapper_arm.so',
                        'libs/arm64-v8a/libEGL_wrapper_arm64.so',
                        'libs/x86/libEGL_wrapper_x86.so',
                        'libs/armeabi-v7a/libGLESv1_CM_wrapper_arm.so',
                        'libs/arm64-v8a/libGLESv1_CM_wrapper_arm64.so',
                        'libs/x86/libGLESv1_CM_wrapper_x86.so',
                        'libs/armeabi-v7a/libGLESv2_wrapper_arm.so',
                        'libs/arm64-v8a/libGLESv2_wrapper_arm64.so',
                        'libs/x86/libGLESv2_wrapper_x86.so',
                        'libs/armeabi-v7a/libGLES_wrapper_arm.so',
                        'libs/arm64-v8a/libGLES_wrapper_arm64.so',
                        'libs/x86/libGLES_wrapper_x86.so',
                        'egl.cfg'
                    ),
                    'update-version-functions': [],
                },
                {
                    'name': 'eglretrace',
                    'binaries': (
                        'bin/eglretrace-release.apk',
                    ),
                    'update-version-functions': [update_android_versions]
                },
            ],
        },
    }

    for product_name in product_names:
        product = products[product_name]
        # Create install dir
        if not install_base_dir:
            install_dir = os.path.abspath(os.path.join('install', product['name'], 'android', 'release'))
        else:
            install_dir = install_base_dir

        if not os.path.exists(install_dir):
            os.makedirs(install_dir)

    # Obtain version from CMakeLists.txt
    cmake = cmake_dict(src_path)
    version_major = int(cmake['PATRACE_VERSION_MAJOR'])
    version_minor = int(cmake['PATRACE_VERSION_MINOR'])
    version_patch = int(cmake['PATRACE_VERSION_PATCH'])

    svn_revision = os.environ.get('SVN_REVISION', 'unofficial')
    version_type = os.environ.get('VERSION_TYPE', 'dev')

    # Update version information. This modifies e.g. AndroidManifest.xml
    # so must be done before update_android_projects() below.
    for product_name in product_names:
        product = products[product_name]
        for target in product['targets']:
            android_target_dir = os.path.join(product['android_root'], target['name'])
            # Generate version information
            for version_function in target['update-version-functions']:
                version_function(
                    version_major, version_minor, version_patch, svn_revision, version_type,
                    source_root=product['source_root'],
                    cmake_script=os.path.join(product['cmake_root'], target['name'], 'config.cmake'),
                    android_target_dir=android_target_dir
                )

    # Update Android project (runs "android update project")
    update_android_projects(src_path)

    for product_name in product_names:
        product = products[product_name]

        for target in product['targets']:
            print "*" * 70
            print "Building {}/{}".format(product['name'], target['name'])
            print "*" * 70
            android_target_dir = os.path.join(product['android_root'], target['name'])

            # Build
            run_command('make -j8 -C {makedir}'.format(makedir=android_target_dir))

            # Install
            target_install_dir = os.path.join(install_dir, target['name'])
            if not os.path.exists(target_install_dir):
                os.makedirs(target_install_dir)

            for binary in target['binaries']:
                install(
                    os.path.join(android_target_dir, binary),
                    target_install_dir
                )

    return SUCCESS


def main():
    # Parse options
    parser = OptionParser()

    (options, args) = parser.parse_args()

    # Ser directory variables
    script_dir = os.path.dirname(os.path.realpath(__file__))
    src_path = os.path.join(script_dir, '..')

    build_base_dir = os.path.join(script_dir, '..', 'builds')
    if not os.path.exists(build_base_dir):
        os.mkdir(build_base_dir)

    install_base_dir = os.path.join(script_dir, '..', 'install')
    if not os.path.exists(install_base_dir):
        os.mkdir(install_base_dir)

    # Build
    build_cmake(src_path, build_base_dir, install_base_dir)
    build_android(src_path, ['patrace'], install_base_dir)


if __name__ == '__main__':
    main()