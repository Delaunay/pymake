#!/usr/bin/env python3

# Finally writing a regression test for ScannerIterator.
#
# davep 16-Nov-2014

import sys
from scanner import ScannerIterator
from vline import VirtualLine

def main() : 
    s = ScannerIterator( "hello, world" )
    for c in s:
        print(c,end="")
    print()

    s = ScannerIterator("hello, world" )
    assert s.next()=='h'
    assert s.next()=='e'
    s.pushback()
    s.pushback()
    assert s.next()=='h'
    assert s.next()=='e'
    s.pushback()
    s.pushback()
    assert s.lookahead()=='h'
    assert s.next()=='h'
    assert s.next()=='e'
    
    s.push_state()
    for c in s :
        if c==' ':
            break
    assert s.remain()=="world"
    s.pop_state()
    assert s.remain()=='llo, world', s.remain()

    del s

    s = ScannerIterator("hello, world")
    for c in s : 
        if c==' ':
            s.stop()
    assert s.remain()==''
    try : 
        s.next()
    except StopIteration:
        pass
    else:
        assert 0
    del s

    s = ScannerIterator( "  hello, world" )
    s.lstrip()
    assert s.remain()=='hello, world'
    s.eat('hello')
    assert s.remain()==', world'
    del s

    s = ScannerIterator( "  hello, world" )
    try : 
        s.eat("hello")
    except ValueError:
        pass
    else:
        assert 0
    del s

    s = ScannerIterator( "  hello, world" )
    s.lstrip().eat("hello,").lstrip()
    assert s.remain()=="world"
    del s

    s = ScannerIterator( "" )
    try : 
        s.eat("hello")
    except ValueError:
        pass
    else:
        assert 0
    del s

    vline = VirtualLine(["   hello,world"],0)
    viter = iter(vline)
    viter.lstrip()
    print(str(viter.remain()))
    assert viter.remain()=="hello,world", str(viter)

if __name__=='__main__':
    main()

