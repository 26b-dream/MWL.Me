from __future__ import annotations


def extend_class(original_class: object, extended_class: object):
    # Get a list of all of the functions
    original_functions = dir(original_class)

    # Go through all the function in the extended class
    for function in dir(extended_class):
        # If the function does not exist patch it in
        if function not in original_functions:
            setattr(original_class, function, getattr(extended_class, function))
