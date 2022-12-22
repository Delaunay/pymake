#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0

import os
import tempfile
import subprocess

import run

_debug = True

#
#  printenv will have non-zero exit code if the variable doesn't exist. 
#  The subprocess.run_test() will raise error on non-zero exit.
#
def should_succeed(makefile, extra_args=None, extra_env=None):
    with tempfile.NamedTemporaryFile() as outfile:
        outfile.write(makefile.encode("utf8"))
        outfile.flush()
        test_output = run.run_pymake(outfile.name, extra_args, extra_env)
    return test_output.decode("utf8")

def verify(output_str, expect):
    all_lines = output_str.split("\n")
    for line,expect_line in zip(all_lines,expect):
        if _debug:
            print("\"%s\" == \"%s\"" % (line, expect_line))
        assert line==expect_line, (line,expect_line)

def run_test(makefile, expect):
    output = should_succeed(makefile)
    verify(output,expect)

def test1():
    makefile = """
CC=gcc
export CC
all:
	printenv CC
"""
    expect = ("printenv CC", "gcc")
    run_test(makefile,expect)

def test_simple_assign():
    makefile = """
export CC=gcc
all:
	printenv CC
"""
    expect = ("printenv CC", "gcc")
    run_test(makefile,expect)

def test_multiple_assign():
    makefile = """
export CC=gcc
export CFLAGS=-Wall
all:
	printenv CC CFLAGS
"""
    expect = ("printenv CC CFLAGS", "gcc", "-Wall")
    run_test(makefile,expect)

def test_multiple_export():
    makefile = """
CC=gcc
CFLAGS=-Wall
export CC CFLAGS
all:
	printenv CC CFLAGS
"""
    expect = ("printenv CC CFLAGS", "gcc", "-Wall")
    run_test(makefile, expect)

def test_whitespace():
    makefile = """
            export              CC =  gcc
		export	CFLAGS	=	-Wall
all:
	printenv CC CFLAGS
"""
    expect = ("printenv CC CFLAGS", "gcc", "-Wall")
    run_test(makefile, expect)

def test_export_everything():
    makefile = """
CC=gcc
CFLAGS=-Wall
export
CXXFLAGS=-std=c++20
all:
	printenv CC CFLAGS CXXFLAGS
"""
    # make sure to have a variable set after the export statement to verify new
    # vars are marked for export, too
    expect = ("printenv CC CFLAGS CXXFLAGS", "gcc", "-Wall", "-std=c++20")
    run_test(makefile, expect)

def test_export_environment_vars():
    # All environment variables will be marked for export.
    # "By default, only variables that came from the environment or the
    # command line are passed to recursive invocations."
    #  -- GNU Make manual  Version 4.3 Jan 2020
    makefile = """
CC=gcc
CFLAGS=-Wall
export
all:
	printenv CC CFLAGS
"""
    # environment vars do not override internal vars
    os.environ["CC"] = "xcc"
    expect = ("printenv CC CFLAGS", "gcc", "-Wall")
    run_test(makefile, expect)
    del os.environ["CC"]

def test_export_varname():
    # "export" isn't a keyword so can be used as a variable name, too
    # (/me shakes fist at Make)
    makefile = """
export:=42
$(info export=$(export))
all:
"""
    expect = ("export=42",)
    run_test(makefile, expect)

def test_double_export():
    # can only have one expression per export
    makefile="""
export FOO=BAR BAZ=QUX
all:
	printenv FOO
"""
    expect = ("printenv FOO", "BAR BAZ=QUX",)
    run_test(makefile, expect)

def test_env_var_export():
    # "By default, only variables that came from the environment or the
    # command line are passed to recursive invocations."
    # -- GNU Make manual  Version 4.3 Jan 2020

    # verify all environment variables are exported
    makefile = """
FOO=bar
export FOO
all:
	printenv FOO BAR
"""
    expect = ("printenv FOO BAR", "bar", "baz")
    output = should_succeed(makefile, extra_env={"BAR":"baz"})
    verify(output,expect)

def test_command_line_export():
    # "By default, only variables that came from the environment or the
    # command line are passed to recursive invocations."
    # -- GNU Make manual  Version 4.3 Jan 2020

    # verify all command line args are exported
    makefile = """
FOO=bar
export FOO
all:
	printenv FOO BAR
"""
    expect = ("printenv FOO BAR", "bar", "baz")
    output = should_succeed(makefile, extra_args=("BAR=baz",))
    verify(output,expect)

def test_command_line_override():
    # command line var value overrides file var
    makefile = """
CFLAGS=-Wall
export CFLAGS
all:
	printenv CFLAGS
"""
    expect = ("printenv CFLAGS", "-Wextra")
    output = should_succeed(makefile, extra_args=("CFLAGS=-Wextra",))
    verify(output,expect)

if __name__ == '__main__':
    test1()
#    test_multiple_assign()
#    test_export_everything()
#    test_export_environment_vars()
#    test_command_line_export()
