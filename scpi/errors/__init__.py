"""SCPI module specific errors"""


class CommandError(RuntimeError):
    def __init__(self, command, code, message, *args, **kwargs):
        self.command = command
        self.code = code
        self.message = message
        super(CommandError, self).__init__(str(self), *args, **kwargs)

    def __str__(self):
        return "'%s' returned error %d: %s" % (self.command, self.code, self.message)
