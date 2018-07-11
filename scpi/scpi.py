"""Generic SCPI commands, allow sending and reading of raw data, helpers to parse information"""
import asyncio
import decimal
import re

from async_timeout import timeout

from .errors import CommandError

COMMAND_DEFAULT_TIMEOUT = 1.0
ERROR_RE = re.compile(r'([+-]\d+),"(.*?)"')


class SCPIProtocol(object):
    """Implements the SCPI protocol talks over the given transport"""
    transport = None
    lock = asyncio.Lock()

    def __init__(self, transport):
        self.transport = transport

    async def quit(self):
        """Shuts down any background threads that might be active"""
        await self.transport.quit()

    async def abort_command(self):
        """Shortcut to the transports abort_command call"""
        await self.transport.abort_command()

    async def get_error(self):
        """Asks for the error code and string"""
        response = await self.ask('SYST:ERR?')
        match = ERROR_RE.search(response)
        if not match:
            # PONDER: Make our own exceptions ??
            raise ValueError("Response '{:s}' does not have correct error format".format(response))
        code = int(match.group(1))
        errstr = match.group(2)
        return (code, errstr)

    async def check_error(self, prev_command=''):
        """Check for error and raise exception if present"""
        code, errstr = await self.get_error()
        if code != 0:
            raise CommandError(prev_command, code, errstr)

    async def command(self, command, cmd_timeout=COMMAND_DEFAULT_TIMEOUT, abort_on_timeout=True):
        """Sends a command, does not wait for response"""
        try:
            with timeout(cmd_timeout):
                with (await self.lock):
                    await self.transport.send_command(command)
        except asyncio.TimeoutError as e:
            # check for the actual error if available
            await self.check_error(command)
            if abort_on_timeout:
                self.abort_command()
            # re-raise the timeout if no other error found
            raise e
        # other errors are allowed to bubble-up as-is

    async def safe_command(self, command, *args, **kwargs):
        """See "command", this just auto-checks for errors each time"""
        await self.command(command, *args, **kwargs)
        await self.check_error(command)

    async def ask(self, command, cmd_timeout=COMMAND_DEFAULT_TIMEOUT, abort_on_timeout=True):
        """Send a command and waits for response, returns the response"""
        try:
            with timeout(cmd_timeout):
                with (await self.lock):
                    response = None

                    def set_response(message):
                        nonlocal response
                        response = message
                    self.transport.message_callback = set_response
                    await self.transport.send_command(command)
                    while response is None:
                        await asyncio.sleep(0)
                    return response

        except asyncio.TimeoutError as e:
            # check for the actual error if available
            await self.check_error(command)
            if abort_on_timeout:
                self.abort_command()
            # re-raise the timeout if no other error found
            raise e
        # other errors are allowed to bubble-up as-is

    async def safe_ask(self, command, *args, **kwargs):
        """See "ask", this just autp-checks for errors each time"""
        response = await self.ask(command, *args, **kwargs)
        await self.check_error(command)
        return response


class SCPIDevice(object):
    """Implements nicer wrapper methods for the raw commands from the generic SCPI command set"""
    protocol = None
    command = None
    ask = None

    def __init__(self, protocol, use_safe_variants=True):
        """Initialize device with protocol instance, if use_safe_variants is True (default) then we will
        do the automatic error checking for each command, set to false to take care of it yourself"""
        self.protocol = protocol
        self.command = self.protocol.command
        self.ask = self.protocol.ask
        if use_safe_variants:
            self.command = self.protocol.safe_command
            self.ask = self.protocol.safe_ask

    async def quit(self):
        """Shuts down any background threads that might be active"""
        await self.protocol.quit()

    async def abort(self):
        """Tells the protocol layer to issue "Device clear" to abort the command currently hanging"""
        await self.protocol.abort_command()

    async def get_error(self):
        """Shorthand for procotols method of the same name"""
        return await self.protocol.get_error()

    async def reset(self):
        """Resets the device to known state (with *RST) and clears the error log"""
        return self.protocol.command('*RST;*CLS')

    async def operation_complete(self):
        """Queries for "operation complete" and returns the response"""
        resp = await self.ask('*OPC?')
        return bool(int(resp))

    async def wait_for_complete(self, wait_timeout):
        """Wait for all queued operations to complete (up-to defined timeout)"""
        resp = await self.ask('*WAI;*OPC?', cmd_timeout=wait_timeout)
        return bool(int(resp))

    async def measure_voltage(self, extra_params=""):
        """Returns the measured (scalar) actual output voltage (in volts), pass extra_params string to append to the command (like ":ACDC")"""
        resp = await self.ask("MEAS:SCAL:VOLT%s?" % extra_params)
        return decimal.Decimal(resp)

    async def measure_current(self, extra_params=""):
        """Returns the measured (scalar) actual output current (in amps), pass extra_params string to append to the command (like ":ACDC")"""
        resp = await self.ask("MEAS:SCAL:CURR%s?" % extra_params)
        return decimal.Decimal(resp)

    async def set_measure_current_max(self, amps):
        """Sets the upper bound (in amps) of current to measure, on some devices low-current accuracy can be increased by keeping this low"""
        await self.command("SENS:CURR:RANG %f" % amps)

    async def query_measure_current_max(self):
        """Returns the upper bound (in amps) of current to measure, this is not neccessarily same number as set with set_measure_current_max"""
        resp = await self.ask("SENS:CURR:RANG?")
        return decimal.Decimal(resp)

    async def set_voltage(self, millivolts, extra_params=""):
        """Sets the desired output voltage (but does not auto-enable outputs) in millivolts, pass extra_params string to append to the command (like ":PROT")"""
        await self.command("SOUR:VOLT%s %f MV" % (extra_params, millivolts))

    async def query_voltage(self, extra_params=""):
        """Returns the set output voltage (in volts), pass extra_params string to append to the command (like ":PROT")"""
        resp = await self.ask("SOUR:VOLT%s?" % extra_params)
        return decimal.Decimal(resp)

    async def set_current(self, milliamps, extra_params=""):
        """Sets the desired output current (but does not auto-enable outputs) in milliamps, pass extra_params string to append to the command (like ":TRIG")"""
        await self.command("SOUR:CURR%s %f MA" % (extra_params, milliamps))

    async def query_current(self, extra_params=""):
        """Returns the set output current (in amps), pass extra_params string to append to the command (like ":TRIG")"""
        resp = await self.ask("SOUR:CURR%s?" % extra_params)
        return decimal.Decimal(resp)

    async def set_output(self, state):
        """Enables/disables output"""
        await self.command("OUTP:STAT %d" % state)

    async def query_output(self):
        """Returns the output state"""
        resp = await self.ask("OUTP:STAT?")
        return bool(int(resp))

    async def identify(self):
        """Returns the identification data, standard order is Manufacturer, Model no, Serial no (or 0), Firmware version"""
        resp = await self.ask("*IDN?")
        return resp.split(',')
