@DeprecationWarning
def validateKeys(func):
    def wrapper(self, **kwargs):
        parameter_names = func.__code__.co_varnames[:func.__code__.co_argcount]

        if len(parameter_names) - 1 != len(kwargs):
            raise ValueError("Not the same amount of values!")

        for parameter_name in parameter_names:
            if parameter_name == 'self':
                continue

            if parameter_name not in kwargs:
                raise ValueError("Parameter %s missing!" % parameter_name)

        return func(self, **kwargs)

    return wrapper
