import asyncio
import random
import edzed

def input_temperature():
    """Fake room thermometer (Celsius scale)."""
    t = random.uniform(20.0, 28.0)
    print(f"T={t:.1f}")
    return t

def output_heater(hot):
    if hot:
        print(" T >= 24 °C, heater off")
    else:
        print(" T < 22 °C, heater on")

edzed.ValuePoll(
    'thermometer',
    func=input_temperature, interval=1.5)

edzed.Compare(
    'thermostat',
    low=22.0, high=24.0, on_output=edzed.Event('heater')
    ).connect('thermometer')

edzed.OutputFunc(
    'heater',
    func=output_heater, on_error=None)

if __name__ == '__main__':
    print('Press ctrl-C to stop\n')
    asyncio.run(edzed.run())
