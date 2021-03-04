import asyncio
import random
import edzed

def get_temperature():
    """Fake room thermometer (Celsius scale)."""
    t = random.uniform(20.0, 28.0)
    print(f" T={t:.1f}")
    return t

edzed.ValuePoll(
    'thermometer',
    func=get_temperature, interval=1)
edzed.Compare(
    'thermostat',
    low=22.0, high=24.0, on_output=edzed.Event('heater')
    ).connect('thermometer')
edzed.OutputFunc(
    'heater',
    func=lambda hot: print(f"Heater {'off' if hot else 'on'}"),
    on_error=None
    )

if __name__ == '__main__':
    print('Press ctrl-C to stop')
    circuit = edzed.get_circuit()
    asyncio.run(circuit.run_forever())
