from multiprocessing import Pool, cpu_count
import os
import re
import time
import sys
from subprocess import call


def execute_feature(index, feature, system):
    time.sleep((index % 4) * 1.5)
    call("rake fasttest_acceptance_{}[{}]".format(system, feature), shell=True)

if __name__ == '__main__':
    assert len(sys.argv) == 2
    p = Pool(cpu_count())
    if sys.argv[1] == 'lms':
        array = ['lms/djangoapps/courseware/features/{}'.format(feature) for feature in os.listdir('lms/djangoapps/courseware/features/') if re.match(r'.*\.feature', feature)]
        index = array.index('lms/djangoapps/courseware/features/problems.feature')
        array[0], array[index] = (array[index], array[0])
    else:
        array = ['cms/djangoapps/contentstore/features/{}'.format(feature) for feature in os.listdir('cms/djangoapps/contentstore/features/') if re.match(r'.*\.feature', feature)]
        index = array.index('cms/djangoapps/contentstore/features/problem-editor.feature')
        array[0], array[index] = (array[index], array[0])
        index = array.index('cms/djangoapps/contentstore/features/html-editor.feature')
        array[1], array[index] = (array[index], array[1])
    for index, feature in enumerate(array):
        p.apply_async(execute_feature, args=(index, feature, sys.argv[1]))
    p.close()
    p.join()
