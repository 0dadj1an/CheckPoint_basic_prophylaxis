# CheckPoint_basic_prophylaxis

* script goes via all policies on specified mgmt machine and saving data
* unused objects, rules with zero hitcount, disabled rules, rules with any, rules with hitcount older than specified time
* is possible also run cmd on targets connected to mgmt via run-script API call, in such a case, check main() method and uncomment cmds, by default this is disabled, use provided examples or create own cmd, for more info see:
https://sc1.checkpoint.com/documents/latest/APIs/index.html#cli/run-script~v1.8%20

* run script, follow instructions, see comments if needed, python 3.X ready
* if needed, see logcp.elg log file generated in same path where is script for logs, errors
