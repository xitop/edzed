import asyncio
import edzed

edzed.Timer(
    'clk', comment="clock generator",
    t_period=1.0, on_output=edzed.Event('out'))

def output_print(value):
    if value:
        print('..tock')
    else:
        print('tick..', end='', flush=True)

edzed.OutputFunc(
    'out', func=output_print, on_error=None)

if __name__ == '__main__':
    print('Press ctrl-C to stop\n')
    asyncio.run(edzed.run())
