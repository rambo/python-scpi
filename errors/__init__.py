"""SCPI module specific errors"""

from exceptions import RuntimeError


class TimeoutError(RuntimeError):
    def __init__(self, command, time, *args, **kwargs):
        self.command = command
        self.time = time
        super(TimeoutError, self).__init__(str(self), *args, **kwargs)

    def __str__(self):
        return "'%s' timed out after %f seconds" % (self.command, self.time)

class CommandError(RuntimeError):
    def __init__(self, command, code, message, *args, **kwargs):
        self.command = command
        self.code = code
        self.message = message
        super(CommandError, self).__init__(str(self), *args, **kwargs)

    def __str__(self):
        return "'%s' returned error %d: %s" % (self.command, self.code, self.message)

