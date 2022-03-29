from __future__ import print_function

import glob
import optparse
import os
import random
import shutil
import stat
import string
import subprocess
import time

import irods_python_ci_utilities

def install_test_prerequisites():
    irods_python_ci_utilities.subprocess_get_output(['sudo', 'python3', '-m', 'pip', 'install', 'boto3', '--upgrade'], check_rc=True)
    irods_python_ci_utilities.subprocess_get_output(['sudo', 'python3', '-m', 'pip', 'install', 'minio', '--upgrade'], check_rc=True)
    irods_python_ci_utilities.subprocess_get_output(['sudo', '-EH', 'python3', '-m', 'pip', 'install', 'unittest-xml-reporting==1.14.0'])




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
    install_test_prerequisites()

    install_build_prerequisites()
    minio_processes = download_and_start_minio_server()

    time.sleep(10)

    try:
        test_output_file = 'log/test_output.log'
        irods_python_ci_utilities.subprocess_get_output(['sudo', 'su', '-', 'irods', '-c',
            f'python3 scripts/run_tests.py --xml_output --run_s {test} 2>&1 | tee {test_output_file}; exit $PIPESTATUS'],
            check_rc=True)
        minio_processes[0].terminate()
        minio_processes[1].terminate()
    finally:
        if output_root_directory:
            irods_python_ci_utilities.gather_files_satisfying_predicate('/var/lib/irods/log', output_root_directory, lambda x: True)
            shutil.copy('/var/lib/irods/log/test_output.log', output_root_directory)
            shutil.copytree('/var/lib/irods/test-reports', os.path.join(output_root_directory, 'test-reports'))


if __name__ == '__main__':
    main()
