# davep 20-Mar-2016 ; symbol table

import os
import logging
import collections

import pymake.version as version
import pymake.constants as constants
from pymake.symbolmk import Symbol
from pymake.error import warning_message, MakeError

logger = logging.getLogger("pymake.symtable")

#logger.setLevel(level=logging.DEBUG)

#_fail_on_undefined = True
_fail_on_undefined = False

# classes for vars saved in SymbolTable
class Entry:
    origin = "(invalid origin)"
    never_export = False

    def __init__(self, name, value=None, pos=None):
        logger.debug("create var name=%s origin=%s pos=%r", name, self.origin, pos)
        self.name = name
        self._value = value
        self.pos = pos

        # I'm not sure this is a good idea yet.
#        self.read_only = False

        self._export = False

        # handle appended expressions
        self._appends = []

        # check for recursive variable expansion attempting to expand itself
        self.loop = 0

    @property
    def export(self):
        return self._export

    def set_export(self, value):
        self._export = value

    @property
    def value(self):
        return self._value

    def set_value(self, value, pos):
        # TODO add a stack where the values get changed
        self.pos = pos
        self._value = value

    def sanity(self):
        # TODO
        pass

    def get_pos(self):
        return self.pos

    def eval(self, symbol_table):
        # handle the case where an expression is stored in the symbol table vs
        # a value 
        # e.g.,  a=10  (evaluated whenever $a is used)
        # vs   a:=10  (evaluated immediately and "10" stored in symtable)
        #
        if isinstance(self._value, Symbol):
            logger.debug("recursive eval %r name=%s at pos=%r", self, self.name, self.get_pos())
            if self.loop > 0:
                msg = "Recursive variable %r references itself (eventually)" % self.name
                raise MakeError(description=msg, pos=self.get_pos())
            self.loop += 1
            step1 = [ self._value.eval(symbol_table) ]
            step1.extend( [t.eval(symbol_table) for t in self._appends] )
            self.loop -= 1
            return " ".join(step1)

        return self._value

    def append_recursive(self, value):
        # ha ha type checking
        assert isinstance(value,Symbol), type(value)

        return self._appends.append(value)

class FileEntry(Entry):
    origin = "file"

    def __init__(self, name, value, pos):
        if pos is None:
            # happens with test code
            pos = ("/dev/null", (0,0))
        super().__init__(name, value, pos)

    def sanity(self):
        assert self.pos is not None


# "if variable has a default definition, as is usual with CC and so on. See Section 10.3
# [Variables Used by Implicit Rules], page 119. Note that if you have redefined a
# default variable, the origin function will return the origin of the later definition."
# -- GNU Make manual  Version 4.3 Jan 2020
class DefaultEntry(Entry):
    origin = "default"
    never_export = True

class CallbackEntry(DefaultEntry):
    # Some built-in variables have complex requirements that can't be stored as
    # a simple string in the symbol table. For example .VARIABLES returns a
    # list of the variables currently defined.
    
    def __init__(self, name, callback_fn):
        super().__init__(name)

        # self.eval() will call this fn to get a value
        self.callback_fn = callback_fn

    def eval(self, symbol_table):
        return self.callback_fn(symbol_table)

# Environment Variables higher precedence than File variables.  But Command
# Line args are high precedence than Environment Variables.
# "By default, only variables that came from the environment or the
# command line are passed to recursive invocations."
# -- GNU Make manual  Version 4.3 Jan 2020
class EnvVarEntry(Entry):
    origin = "environment"

    def __init__(self, name, value):
        pos = ("environment",(0,0))
        super().__init__(name,value,pos)
        self.set_export( True )

# Command line args are higher precedence than variables in the makefile except
# if the variable is marked with 'override'
#
# Command Line higher precedence than Environment
#
# "By default, only variables that came from the environment or the
# command line are passed to recursive invocations."
# -- GNU Make manual  Version 4.3 Jan 2020
class CommandLineEntry(Entry):
    origin = "command line"

    def __init__(self, name, value):
        super().__init__(name,value)
        self.set_export(True)

    def set_value(self, value, pos):
        pass


class AutomaticEntry(Entry):
    origin = "automatic"
    never_export = True

    def __init__(self, name, value, pos):
        assert name in constants.automatic_variables, name
        super().__init__(name, value, pos)


class SymbolTable(object):
    def __init__(self, **kwargs):
        # key: variable name
        # value: _entry_template dict instance
        self.symbols = {}

        # push/pop a name/value so $(foreach) (and other functions) can re-use
        # the var name (and we don't have to make a complete new copy of a
        # symbol table just to save/restore a single var)
        self.stack = {}

        self.export_default_value = False

        self.warn_undefined = kwargs.get("warn_undefined_variables", False)

        self._init_builtins()
        self._init_envvars()

        # This is an ugly hack to allow us to treat command line argument
        # expressions transparently as just another AssignmentExpression.
        # When evaluating command line statements, we'll set this flag which
        # will mark the incoming variables as from the command line.
        self.command_line_flag = False

    def _init_builtins(self):
        # key: var name
        # value: symbol table method to return values
#        self.built_ins = {
#            ".VARIABLES" : self.variables,
#        }
        
        # TODO add more internal vars
        self._add_entry(CallbackEntry('.VARIABLES', self.variables))
        self._add_entry(DefaultEntry('MAKE_VERSION', version.Version.vstring()))

    def _init_envvars(self):
        # "Every environment variable that make sees when it starts up is
        # transformed into a make variable with the same name and value."
        # 6.10 Variables from the Environment
        # Page 72. GNU Make Version 4.3 January 2020.

        # read all env vars, add to symbol table
        for k,v in os.environ.items():
            self._add_entry(EnvVarEntry(k,v))

    def _add_entry(self, entry):

        # sanity check the entry fields
        entry.sanity()

        self.symbols[entry.name] = entry

    def add(self, name, value, pos=None):
        logger.debug("store \"%s\"=\"%s\"", name, value)

        # an attempt to store empty string is a bug
        assert isinstance(name,str), type(name)
        if not len(name):
            breakpoint()
        assert len(name)

        # sanity check for bad names XXX add more cases
        # (will hit this if my tokenparser is screwing up)
        assert ' ' not in name, name

        # GNU Make doesn't do this warning
        if name in constants.builtin_variables:
            warning_message(pos, "overwriting built-in variable \"%s\"" % name)

        try:
            entry = self.symbols[name]
            logger.debug("overwrite value name=%s at pos=%r", entry.name, pos)
        except KeyError:
            entry = None

        # if we didn't find it, make it
        if self.command_line_flag:
            # this flag is a weird hack to support vars created by eval()'ing
            # expressions from the command line
            new_entry = CommandLineEntry(name, value)
            # command line vars are always exported until explicitly unexported
        else:
            # command line > file
            if isinstance(entry,CommandLineEntry):
                return

            new_entry = FileEntry(name, value, pos)
            new_entry.set_export(self.export_default_value)

#        if entry is None:
#            if self.command_line_flag:
#                # this flag is a weird hack to support command line vars
#                # implicitly
#                entry = CommandLineEntry(name, value)
#                # command line vars are always exported
#                # TODO unless unexport ?
#            else:
#                entry = FileEntry(name, value, pos)
#                entry.set_export(self.export_default_value)
#        else:
#            logger.debug("overwrite value name=%s at pos=%r", entry.name, pos)
#            entry.set_value(value, pos)

        # XXX not sure read-only is a good idea yet
#        if entry.read_only:
#            raise PermissionDenied(name)

        self._add_entry(new_entry)

    def add_automatic(self, name, value, pos):
        entry = AutomaticEntry(name, value, pos)
        self._add_entry(entry)

    def maybe_add(self, name, value, pos=None):
        # If name already exists in the table, don't overwrite.
        # Used with ?= assignments.
        try:
            self.symbols[name]
            return
        except KeyError:
            pass

        return self.add(name, value, pos)

#    def _maybe_eval(self, entry):
#
#        # handle the case where an expression is stored in the symbol table vs
#        # a value 
#        # e.g.,  a=10  (evaluated whenever $a is used)
#        # vs   a:=10  (evaluated immediately and "10" stored in symtable)
#        #
#        if isinstance(entry.value,Symbol):
#            step1 = [t.eval(self) for t in entry.value]
#            return "".join(step1)
#
#        if isinstance(entry, CallbackEntry):  
#            return entry.callback_fn()
#
#        return entry.value

    def _parse_abbrev_patsubst(self, key):
        # This function handles the case of an abbrevitated patsubst.
        # OBJ=$(SRC:.c=.o)  # need to parse out to ("SRC", ".c", ".o)
        #
        # key should be a Python string

        # fast test; allow ValueError to propagate
        colon_pos = key.index(':')
        equal_pos = key.index('=')
        if colon_pos > equal_pos:
            raise ValueError

        varname = key[0:colon_pos]
        pat1 = key[colon_pos+1:equal_pos]
        pat2 = key[equal_pos+1:]

        return (varname,pat1,pat2)

    def _eval_abbrev_patsubst(self, key):
        # allow exception(s) to propagate
        varname, pat1, pat2 = self._parse_abbrev_patsubst(key)

        pat1_len = len(pat1)
        def maybe_replace(s,pat1,pat2):
            if s.endswith(pat1):
                return s[:-pat1_len] + pat2
            return s
        value = self.fetch(varname)
        new_value = " ".join([maybe_replace(s,pat1,pat2) for s in value.split()])
        return new_value

    def fetch(self, key, pos=None):
        # now try a var lookup 
        # Will always return an empty string on any sort of failure. 
        logger.debug("fetch key=%r", key)
#        print("fetch key=\"%r\"" % key)
        assert isinstance(key,str), type(key)
        assert len(key)  # empty key bad

        try:
            # check for a "magic" variable name (an abbreviated patsubst)
            # e.g., $(SRC:.c=.o)
            return self._eval_abbrev_patsubst(key)
        except ValueError:
            pass

        # built-in variable ?
#        try:
#            return self.built_ins[key](key)
#        except KeyError:
#            pass

        try:
#            print("fetch value=\"%r\"" % self.symbols[key])
            return self.symbols[key].eval(self)
        except KeyError:
            if self.warn_undefined:
                warning_message(pos, "undefined variable '%s'" % key)
            if _fail_on_undefined:
                raise

        logger.debug("sym=%s not in symbol table", key)
        return ""

    def append(self, name, value, pos=None):
        # ha ha type checking
        assert isinstance(value,Symbol), type(value)

        # "When the variable in question has not been defined before, ‘+=’ acts
        # just like normal ‘=’: it defines a recursively-expanded variable."
        # GNU Make 4.3 January 2020
        if name not in self.symbols:
            return self.add(name, value, pos)

        entry = self.symbols[name]
        if isinstance(entry.value, Symbol):
            return entry.append_recursive(value)

        # simple string append, space separated
        entry.set_value( entry.value+" "+value.eval(self), pos )

    def push(self, name):
        # save current value of 'name' in secure, undisclosed location

        # don't use self.fetch() because will eval the var which could lead to
        # side effects
        if name not in self.symbols:
            # nothing to save
            return

        entry = self.symbols[name]
        # remove the other reference (otherwise 'add' will just update the
        # self.symbols[name] entry which also points to our stack entry)
        del self.symbols[name]
            
        # create the dequeue if doesn't exist
        if not name in self.stack:
            self.stack[name] = collections.deque()

        # push right, pop right (stack)
        logger.debug("push entry=%s", entry.name)
        self.stack[name].append(entry)

    def pop(self, name):
        # restore previous value of 'name' from the secure, undisclosed location

        # push right, pop right (stack)
        # allow KeyError and IndexError to propagate (indicates a bug in the
        # calling code)
        logger.debug("pop name=%s", name)

        # The stack will contain values previously in the symbol table.
        # If there was no previous value in the symbol table, there will be no
        # entry for it in the stack. In this case, just delete the value from
        # the symbol table.
        # For example, the $(call) function will push each arg $1 $2 $3 $4 etc
        # then pop them after the call.  Very likely $1 $2 $3, etc, are not in
        # the symbol table originally.
        try:
            entry = self.stack[name].pop()
        except KeyError:
            # allow KeyError to propagate if the name doesn't exist in the
            # self.symbols{} because that would be a bug  (this might change in
            # the future)
            del self.symbols[name]
            return

        # TODO future memory optimization would be to delete the dequeue from
        # self.stack when empty

        # restore previous value
        self.symbols[name] = entry

    def flavor(self, name):
        # Support for the $(flavor) function
        #
        # undefined
        # recursive
        # simple

        # don't use self.fetch() because will eval the var which could lead to
        # side effects
        try :
            value = self.symbols[name]
        except KeyError:
            return "undefined"

        if isinstance(value,Symbol):
            return "recursive"

        # TODO dig into gnu make code, learn why env vars return "recursive"
        if value.origin == 'environment':
            return "recursive"

        return "simple"

    def origin(self, name):
        # support for the $(origin) function

        # don't use self.fetch() because will eval the var which could lead to
        # side effects

        # undefined
        # default TODO
        # environment
        # environment override TODO
        # file 
        # command line
        # override -- override directive TODO
        # automatic -- defined in a rule e.g., $@ TODO

        try :
            entry = self.symbols[name]
            assert entry.origin is not None, name
            return entry.origin
        except KeyError:
            return "undefined"

#        try:
#            callback_fn = self.built_ins[name]
#            return "default"
#        except KeyError:
#            return "undefined"

    def value(self, name):
        # support for the $(value) function

        # don't use self.fetch() because will eval the var which could lead to
        # side effects

        try :
            entry = self.symbols[name]
            value = entry.value
            if isinstance(value,Symbol):
                return value.makefile()
            return value
        except KeyError:
            pass

    def variables(self, _):
        # return $(.VARIABLES)
        return " ".join(self.symbols.keys())

    def is_defined(self, name):
        # is this varname in our symbol table (or other mechanisms)
        return name in self.symbols
        
    def export(self, name=None):
        if name is None:
            # export everything
            self._export_all()
            return

        try:
            value = self.symbols[name]
            value.set_export(True)
        except KeyError:
            # no such entry
            return

    def unexport(self, name=None):
        if name is None:
            # export everything
            self._unexport_all()
            return

        try:
            value = self.symbols[name]
            value.set_export(False)
        except KeyError:
            # no such entry
            return

    def undefine(self, name):
        # support the undefine directive
        try:
            entry = self.symbols[name]
        except KeyError:
            # does not exist. no harm, no foul.
            return

        # TODO any variables that GNU Make considers an error to undefine?

        del self.symbols[name]

    def _export_all(self):
        for k,v in self.symbols.items():
            if not v.never_export:
                v.set_export( True )
        # new vars from this point on will be marked as export
        self.export_start()

    def _unexport_all(self):
        for k,v in self.symbols.items():
            if not v.never_export:
                v.set_export(False)
        # new vars from this point on will be marked as export
        self.export_stop()

    def get_exports(self):
        return { name:entry.eval(self) for name,entry in self.symbols.items() if entry.export }

    def export_start(self):
        # The export start/stop allows us to separate the "export" and
        # assignment expressions. We set the "start" before eval()'ing an
        # export with an assignment expression so any assigments in the
        # expression will be automatically marked as 'export'
        #
        # Also used with eval'ing command line arguments which are exported by
        # default.
        # 
        # "By default, only variables that came from the environment or the
        # command line are passed to recursive invocations."
        #  -- GNU Make manual  Version 4.3 Jan 2020
        self.export_default_value = True

    def export_stop(self):
        self.export_default_value = False

    def command_line_start(self):
        # yuk ugly hack
        self.command_line_flag = True

    def command_line_stop(self):
        self.command_line_flag = False

