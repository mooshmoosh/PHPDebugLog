# PHPDebugLog

Two sentence description
------------------------

A massively stripped down XDebug Client that breaks at every line, and logs the contents of every variable at every line. It enables more automated, vs interactive debugging.

Main aims of the project
------------------------

Search through your PHP application, not just for a string in the source code, but a value of a variable at any point throughout the program's execution.

Follow the execution of a PHP application forwards, or backwards.

Create a text file that describes the behaviour of your application, so you can make refactoring changes and know if you've broken the application. (For example if you're working on one of the vast majority of PHP projects written by people who have yet to discover unit tests)

The problem
-----------

I've used IDEs like PHPStorm for debugging and the main problems I come up against are:

I can't be interrupted while debugging, it's not something I can leave and come back to.

I hit the wrong key (F7 vs F8 vs F9) and accidentally step over the function I wanted to look at. This means I have to start the debugging session from scratch.
 
I'm searching for where a variable has its value corrupted as follows:

 + Step over the current statement
 + Has it changed yet?
   + if no, repeat
   + if yes, you stepped over the crucial function. Start again and get to this same point but step in next time.

With each iteration of this loop, the PHP interpreter has to evaluate all the code leading up to the point I'm searching for. This process can take up to a minute or longer.

Solution
--------

This python script solves these problems by turning PHP debugging from something you do with an interactive program to a text file manipulation problem. Define the files you care about, the variables you don't care about, run the script, and hit your application with a HTTP request. The script will, for each breakpoint you define (or, if you don't specify lines, every line) print the value of every variable in memory.

How to use
----------

Create a configuration file modelled on config.json in the root directory of the project. The whole file should contain a json object with the following properties:

 + "files"
   + A JSON array of Objects with the following properties:
     + "local"
       + The filename of a local copy of the file you want to analyze.
     + "remote"
       + The filename of the same file on the remote server.
     + "ignore_variables" (optional)
       + An array of variable names that should not be included in analysis. Ignoring variables can make the script faster. You can use properties of variables. For example: "$this->prop" will exclude "$this->prop" and all its sub properties, but include any properties in $this not called "prop." If this is empty, all variables will be included.
     + "lines" (optional)
       + an array of integers representing lines to break and report the state of the system at. If this is empty, all lines in the file will have breakpoints.

Then run the following command

    ./phpdebuglog.py config.json

Then run the PHP program with debugging enabled. (For example using [a firefox plugin](https://addons.mozilla.org/en-us/firefox/addon/the-easiest-xdebug/)

Pull requests
-------------

Pull requests are welcome. The focus for changes should be around the following:

 + Allowing changes to the formatting of output
 + Improving the API to allow better integration with other applications

The scope for this project should not go beyond making one giant log file containing the entire evolution of a PHP Application's execution. There are many debugging applications out there that try to be everything to everyone. This one simple task is always overlooked, yet makes debugging, and scripted code analysis so much easier.

Obvious Questions
-----------------

Q. Why is it written in python? Most PHP tools are written in PHP.
A. PHP is awful, the whole point is to write less of it.

Q. How does it deal with circular references?
A. When it gets the value of a variable it also gets its address in memory. It keeps a record of all the memory addresses it has "visited" and the name of the variable located there. When it evaluates a variable it has already visited it returns "Reference to {name}."

This does however raise an interesting problem. Consider the following illustrative PHP code

    $EmployeeRecord = stdClass();
    $EmployeeRecord->Contact = stdClass();

    $employeeName = "Gerald"

    $EmployeeRecord->Contact->name = &$employeeName;

A perfectly plausible way to report this is as follows:

    $EmployeeRecord->Contact->name = "Gerald"
    $employeeName = Reference to $EmployeeRecord->Contact->name

Rather than the probably easier to understand

    $EmployeeRecord->Contact->name = Reference to $employeeName
    $employeeName = "Gerald"

To address this issue we search through all the variables in memory in Breadth-first-search order, then print them out in Depth-first-search order. There is no perfect clean solution, but the approach I've taken seems to give results that are pretty much what I expect.
