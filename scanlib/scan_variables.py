import logging
import argparse
import json

log = logging.getLogger(__name__)

def update_variable_dict(variableDict, description="Execute a TXM scan"):
    """Update the variable dictionary based on command-line arguments."""
    # Prepare the command line argument parser
    parser = argparse.ArgumentParser(description=description,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('json_string', nargs="?",
                        help='JSON string with new arguments. '
                             'Used for calling scripts from GUI.')
    for key, default in variableDict.items():
        parser.add_argument('--' + key, default=default, help='Scan parameter.')
    # Extract the arguments
    args = parser.parse_args()
    # Passed as one big JSON string
    if args.json_string:
        argDic = json.loads(args.json_string)
    else:
        argDic = vars(args)
        argDic.pop('json_string')
        print(argDic)
    # Update the variable dictionary with the new values
    log.debug('Orig variable dict: %s', variableDict)
    for k, v in argDic.items():
        variableDict[k] = v
    log.debug('New variable dict: %s', variableDict)
    return variableDict


def old_function():
    argDic = {}
    if len(sys.argv) > 1:
        strArgv = sys.argv[1]
        print(strArgv)
        argDic = json.loads(strArgv)
    log.debug('Orig variable dict: %s', variableDict)
    for k, v in argDic.iteritems():
        variableDict[k] = v
    log.debug('New variable dict: %s', variableDict)
