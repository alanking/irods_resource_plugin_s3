from __future__ import print_function

import optparse
import os
import shutil
import glob
import time
import random
import string
import subprocess

import irods_python_ci_utilities


def get_build_prerequisites_apt():
    return[]

def get_build_prerequisites_yum():
    return[]

def get_build_prerequisites_zypper():
    return[]


def get_build_prerequisites():
    dispatch_map = {
        'Ubuntu': get_build_prerequisites_apt,
        'Centos': get_build_prerequisites_yum,
        'Centos linux': get_build_prerequisites_yum
    }
    try:
        return dispatch_map[irods_python_ci_utilities.get_distribution()]()
    except KeyError:
        irods_python_ci_utilities.raise_not_implemented_for_distribution()


def install_build_prerequisites():
    irods_python_ci_utilities.subprocess_get_output(['sudo', 'pip', 'install', 'boto3', '--upgrade'], check_rc=True)
    irods_python_ci_utilities.subprocess_get_output(['sudo', 'pip', 'install', 'minio==6.0.2', '--upgrade'], check_rc=True)
    irods_python_ci_utilities.subprocess_get_output(['sudo', '-EH', 'pip', 'install', 'unittest-xml-reporting==1.14.0'])
    if irods_python_ci_utilities.get_distribution() == 'Ubuntu': # cmake from externals requires newer libstdc++ on ub12
        if irods_python_ci_utilities.get_distribution_version_major() == '12':
            irods_python_ci_utilities.install_os_packages(['python-software-properties'])
            irods_python_ci_utilities.subprocess_get_output(['sudo', 'add-apt-repository', '-y', 'ppa:ubuntu-toolchain-r/test'], check_rc=True)
            irods_python_ci_utilities.install_os_packages(['libstdc++6'])

    #irods_python_ci_utilities.install_os_packages(get_build_prerequisites())

def download_and_start_minio_server():

    subprocess.check_output(['wget',  'https://dl.min.io/server/minio/release/linux-amd64/minio'])
    subprocess.check_output(['chmod', '+x', 'minio'])

    access_key = ''.join(random.choice(string.letters) for i in xrange(10))
    secret_key = ''.join(random.choice(string.letters) for i in xrange(10))

    with open('/var/lib/irods/minio.keypair', 'w') as f:
        f.write('%s\n' % access_key)
        f.write('%s\n' % secret_key)

    os.environ['MINIO_ACCESS_KEY'] = access_key
    os.environ['MINIO_SECRET_KEY'] = secret_key

    proc1 = subprocess.Popen(['./minio', 'server', '/data'])

    os.environ['MINIO_REGION_NAME'] = 'eu-central-1'
    proc2 = subprocess.Popen(['./minio', 'server', '--address', ':9001', '/data2'])

    return (proc1, proc2)


def main():
    parser = optparse.OptionParser()
    parser.add_option('--output_root_directory')
    parser.add_option('--built_packages_root_directory')
    options, _ = parser.parse_args()

    output_root_directory = options.output_root_directory
    built_packages_root_directory = options.built_packages_root_directory
    package_suffix = irods_python_ci_utilities.get_package_suffix()
    os_specific_directory = irods_python_ci_utilities.append_os_specific_directory(built_packages_root_directory)

    irods_python_ci_utilities.install_os_packages_from_files(glob.glob(os.path.join(os_specific_directory, 'irods-resource-plugin-s3*.{0}'.format(package_suffix))))

    install_build_prerequisites()
    minio_processes = download_and_start_minio_server()

    time.sleep(10)

    try:
        test_output_file = 'log/test_output.log'
        irods_python_ci_utilities.subprocess_get_output(['sudo', 'su', '-', 'irods', '-c', 'python2 scripts/run_tests.py --xml_output --run_s test_irods_resource_plugin_s3_minio 2>&1 | tee {0}; exit $PIPESTATUS'.format(test_output_file)], check_rc=True)
        minio_processes[0].terminate()
        minio_processes[1].terminate()
    finally:
        if output_root_directory:
            irods_python_ci_utilities.gather_files_satisfying_predicate('/var/lib/irods/log', output_root_directory, lambda x: True)
            shutil.copy('/var/lib/irods/log/test_output.log', output_root_directory)
            shutil.copytree('/var/lib/irods/test-reports', os.path.join(output_root_directory, 'test-reports'))


if __name__ == '__main__':
    main()
