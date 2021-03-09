import asyncio
import edzed

edzed.Timer('clk', comment="clock generator", t_on=0.5, t_off=0.5, on_output=edzed.Event('out'))
edzed.OutputFunc('out', func=lambda value: print('..tock' if value else 'tick..'), on_error=None)

if __name__ == '__main__':
    print('Press ctrl-C to stop')
    circuit = edzed.get_circuit()
    asyncio.run(circuit.run_forever())
