import asyncio
import curses
import os
from itertools import cycle
from random import randint, choice, random
from time import time, sleep

from curses_tools import draw_frame, read_controls, get_frame_size

TIC_TIMEOUT = 0.1


async def blink(canvas, row, column, symbol='*'):
    timing = [2.0, 0.3, 0.5, 0.3]
    nexttime = time() + round(random() * 3, 1)
    while True:
        canvas.addstr(row, column, symbol, curses.A_DIM)
        nexttime += timing[0]
        while time() < nexttime:
            await asyncio.sleep(0)
        canvas.addstr(row, column, symbol)
        nexttime += timing[1]
        while time() < nexttime:
            await asyncio.sleep(0)
        canvas.addstr(row, column, symbol, curses.A_BOLD)
        nexttime += timing[2]
        while time() < nexttime:
            await asyncio.sleep(0)
        canvas.addstr(row, column, symbol)
        nexttime += timing[2]
        while time() < nexttime:
            await asyncio.sleep(0)


async def fire(canvas, start_row, start_column, rows_speed=-0.5, columns_speed=0):
    """Display animation of gun shot, direction and speed can be specified."""
    row, column = start_row, start_column
    canvas.addstr(round(row), round(column), '*')
    await asyncio.sleep(0)
    canvas.addstr(round(row), round(column), 'O')
    await asyncio.sleep(0)
    canvas.addstr(round(row), round(column), ' ')
    row += rows_speed
    column += columns_speed
    symbol = '-' if columns_speed else '|'
    rows, columns = canvas.getmaxyx()
    max_row, max_column = rows - 1, columns - 1
    curses.beep()
    while 1 < row < max_row and 1 < column < max_column:
        canvas.addstr(round(row), round(column), symbol)
        await asyncio.sleep(0)
        canvas.addstr(round(row), round(column), ' ')
        row += rows_speed
        column += columns_speed


async def rocket(canvas, rocket_param):
    frames = rocket_param['frames']
    position = rocket_param['position']
    frame_gen = cycle(frames)
    while True:
        frame_position = position.copy()
        frame = next(frame_gen)
        draw_frame(canvas, frame_position[0], frame_position[1], frame, False)
        await asyncio.sleep(0)
        draw_frame(canvas, frame_position[0], frame_position[1], frame, True)


def load_rocket(canvas):
    frames = []
    for file in ['rocket_frame_1.txt', 'rocket_frame_2.txt']:
        with open(os.path.join('files', file), 'r') as frame:
            frames.append(str(frame.read()))
    frame_size = list(map(lambda a, b: max(a, b), get_frame_size(frames[0]), get_frame_size(frames[1])))
    workspace = list(map(lambda a, b: a - b - 1, list(canvas.getmaxyx()), frame_size))
    position = [workspace[i] // 2 for i in range(2)]
    return {'frames': frames, 'workspace': workspace, 'position': position}


def draw(canvas):
    curses.curs_set(False)
    canvas.nodelay(True)
    canvas.border()
    workspace = [i - 2 for i in list(canvas.getmaxyx())]
    unic_point = set((randint(1, workspace[0]), randint(1, workspace[1])) for _ in range(110))
    corutines = [blink(canvas, point[0], point[1], symbol=choice('+*.:'[:])) for point in unic_point]
    rocket_param = load_rocket(canvas)
    corutines.append(rocket(canvas, rocket_param))
    while True:
        for cor in corutines:
            try:
                cor.send(None)
            except StopIteration:
                corutines.remove(cor)
        canvas.refresh()
        sleep(TIC_TIMEOUT)
        commands = read_controls(canvas)
        rocket_param['position'][0] = min(max(rocket_param['position'][0] + commands[0]*2, 1),
                                          rocket_param['workspace'][0])
        rocket_param['position'][1] = min(max(rocket_param['position'][1] + commands[1]*2, 1),
                                          rocket_param['workspace'][1])
        if commands[2] and rocket_param['position'][0] > 2:
            corutines.append(fire(canvas, rocket_param['position'][0] - 1, rocket_param['position'][1] + 2))


if __name__ == '__main__':
    curses.update_lines_cols()
    curses.wrapper(draw)
