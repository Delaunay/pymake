#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0

import os
import tempfile
import subprocess

import run

_debug = True

def should_succeed(makefile):
    with tempfile.NamedTemporaryFile() as outfile:
        outfile.write(makefile.encode("utf8"))
        outfile.flush()
        test_output = run.run_pymake(outfile.name)
    return test_output.decode("utf8")

def test1():
    makefile="""
FOO=bar
$(info $(origin FOO))
@:;@:
"""
    output = should_succeed(makefile).strip()
    assert output == "file", output
    
def test_var_undefined():
    makefile="""
$(info $(origin FOO))
@:;@:
"""
    output = should_succeed(makefile).strip()
    assert output == "undefined", output

def test_environment_variable():
    makefile="""
$(info $(origin PATH))
@:;@:
"""
    output = should_succeed(makefile).strip()
    assert output == "environment", output

def test_command_line():
    makefile="""
$(info $(origin FOO))
@:;@:
"""
    with tempfile.NamedTemporaryFile() as outfile:
        outfile.write(makefile.encode("utf8"))
        outfile.flush()
        test_output = run.run_pymake(outfile.name, args=("FOO=BAR",))
    assert test_output.decode("utf8").strip() == "command line", test_output

