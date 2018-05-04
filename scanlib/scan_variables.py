import logging
import argparse
import json

log = logging.getLogger(__name__)


def parse_list_variable(raw_value, dtype=float):
    """Parse an variableDict entry into a string.

    Parameters
    ----------
    raw_value
      The input to be parsed. Will probably be either a float or a
      comma-separated string.
    dtype : optional
      What datatype to convert the list into.

    """
    if hasattr(raw_value, 'split'):
        # Process string separated by commas
        out = [x for x in raw_value.split(',')]
    elif hasattr(raw_value, '__iter__'):
        # Process iterables
        out = raw_value
    else:
        # Process a single value
        out = [raw_value]
    # Convert to correct dtype
    out = tuple(dtype(x) for x in out)
    return out


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
