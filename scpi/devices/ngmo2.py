"""Class to handle communicating with the Rohde and Schwarz NGMO2 PSU"""
import decimal

from ..scpi import SCPIDevice

class Output:
    """Enum to represent A and B outputs on the supply"""
    A = 'A'
    B = 'B'

class NGMO2(SCPIDevice):
    """NGMO2 Power supply"""

    async def set_voltage(self, output, volts, extra_params=""):
        """Sets the desired output voltage in volts, output is Output.A or Output.B
        pass extra_params string to append to the command (like ":PROT")"""
        await self.command("SOUR:%s:VOLT%s %0.3f" % (output, extra_params, volts))

    async def set_current_limit(self, output, amps, extra_params=""):
        """Sets the desired current limit in volts, output is Output.A or Output.B
        pass extra_params string to append to the command (like ":PROT")"""
        await self.command("SOUR:%s:CURR%s %0.3f" % (output, extra_params, amps))

    async def enable_output(self, output):
        """Enables the desired output (A or B)"""
        await self.command("OUTP:%s:STAT ON" % output)

    async def disable_output(self, output):
        """Disables the desired output (A or B)"""
        await self.command("OUTP:%s:STAT OFF" % output)

    async def configure_static_current_measurment(self, output):
        """Configures the static current measurement"""
        await self.command("SENS:%s:FUNC CURR" % (output))

    async def get_current(self, output, extra_params=""):
        """Returns the current being drawn from the output"""
        resp = await self.ask("MEAS:%s:CURR%s?" % (output, extra_params))
        return decimal.Decimal(resp)

    async def set_auto_ranging_current(self, output):
        """Sets the desired output voltage in volts, output is Output.A or Output.B
        pass extra_params string to append to the command (like ":PROT")"""
        await self.command("SENS:%s:CURR:RANG AUTO" % (output))

    async def set_medium_ranging_current(self, output):
        """Sets the current ranging to 0.5A mode"""
        await self.command("SENS:%s:CURR:RANG MEDIUM" % (output))

    async def set_high_ranging_current(self, output):
        """Sets the current ranging to -4A/+7A mode, needed for negative readings"""
        await self.command("SENS:%s:CURR:RANG HIGH" % (output))

    async def set_low_ranging_current(self, output):
        """Sets the current ranging to -4A/+7A mode, needed for negative readings"""
        await self.command("SENS:%s:CURR:RANG LOW" % (output))

    async def set_static_measure_interval(self, output, interval_ms):
        """Sets the static current measurement interval in ms"""
        await self.command("SENS:%s:MEAS:INT %0.3f" % (output, interval_ms/1000))

    async def set_static_measure_count(self, output, count):
        """Sets the static current measurement average count"""
        await self.command("SENS:%s:AVER:COUN %d" % (output, count))

    async def reset_factory_default_settings(self):
        """Resets the supply to factory default settings"""
        await self.command("SENS:A:PULS:STAR OFF")
        await self.command("SENS:B:PULS:STAR OFF")
        await self.command("*RCL 0")

    async def clear_error_queue(self):
        """Clears the device error queue"""
        await self.command("*CLS")

    async def set_display_channel(self, output):
        """Sets the channel shown on the display"""
        await self.command("DISP:CHAN %s" % output)

    # Dynamic measurements
    async def configure_dynamic_reading(self, output, samples, interval_ms):
        """Configures the dynamic measurement settings"""
        # Sets pulse measurement channel off
        await self.command("SENS:%s:PULS:STAR OFF" % output)
        # Sets the pulse measurement to read current
        await self.command("SENS:%s:PULS:CHAN CURR" % output)
        # Sets the pulse measurement to average readings
        await self.command("SENS:%s:PULS:TYPE AVER" % output)
        # Sets the number of samples to take
        await self.command("SENS:%s:PULS:SAMP:LENG %d" % (output, samples))
        # Sets the trigger to be internal
        await self.command("SENS:%s:PULS:TRIG:SOUR INT" % output)
        # Sets the offset from trigger to start reading from
        await self.command("SENS:%s:PULS:TRIG:OFFS 0" % output)
        # Sets the function to average the readings
        await self.command("SENS:%s:FUNC AVER" % (output))
        # Sets the sample interval
        await self.command("SENS:%s:PULS:SAMP:INT %0.5f" % (output, interval_ms/1000))
        # Sets timeout to be infinite
        await self.command("SENS:%s:PULS:TRIG:TIM INFinite" % output)
        # Sets output format to ASCII
        await self.command("FORM:DATA ASCII")

    async def trigger_dynamic_measurement(self, output):
        """Triggers a dynamic current measurement"""
        await self.command("*%sTRg" % output)

    async def fetch_dynamic_measurement(self, output):
        """Returns the current being drawn from the output"""
        resp = await self.ask("FETCh:%s?" % output)
        return resp

    async def fetch_dynamic_measurement_array(self, output):
        """Returns the current being drawn from the output"""
        resp = await self.ask("FETCh:%s:ARRay?" % output)
        return resp
