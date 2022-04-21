import asyncio
import curses
import os
import time
from itertools import cycle
from random import randint, choice

from curses_tools import draw_frame, read_controls, get_frame_size
from physics import update_speed
from obstacles import Obstacle, show_obstacles
from explosion import explode
from operator import sub

TIC_TIMEOUT = 0.05
COUNT_STARS = 200
ROCKET_SPEED = 2
BULLET_SPEED = 2.5

COROUTINES = []
OBSTACLES = {}
OBSTACLES_IN_LAST_COLLISIONS=[]
GAME_OVER=[False]

async def sleep(tics=1):
    for tic in range(tics):
        await asyncio.sleep(0)


async def blink(canvas, row, column, symbol='*'):
    timing = [2.0, 0.3, 0.5, 0.3]
    tics = [int(delay / TIC_TIMEOUT) for delay in timing]
    await sleep(randint(0, int(sum(timing) / TIC_TIMEOUT)))
    while True:
        canvas.addstr(row, column, symbol, curses.A_DIM)
        await sleep(tics[0])
        canvas.addstr(row, column, symbol)
        await sleep(tics[1])
        canvas.addstr(row, column, symbol, curses.A_BOLD)
        await sleep(tics[2])
        canvas.addstr(row, column, symbol)
        await sleep(tics[3])


async def fire(canvas, start_row, start_column, rows_speed=-BULLET_SPEED, columns_speed=0):
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
        for uid,obstale in OBSTACLES.items():
            if obstale.has_collision(round(row),round(column),round(rows_speed)):
                OBSTACLES_IN_LAST_COLLISIONS.append(uid)
                return
        row += rows_speed
        column += columns_speed


async def fly_rocket(canvas, position, frames):
    frame_gen = cycle(frames)
    height,width=get_max_sizes(frames)
    for frame in frame_gen:
        frame_position = position.copy()
        draw_frame(canvas, frame_position['row'], frame_position['col'], frame, False)
        await asyncio.sleep(0)
        draw_frame(canvas, frame_position['row'], frame_position['col'], frame, True)
        for uid, obstale in OBSTACLES.items():
            if obstale.has_collision(position['row'], position['col'], height,width):
                OBSTACLES_IN_LAST_COLLISIONS.append(uid)
                GAME_OVER[0]=True
                return


async def fly_garbage(canvas, column, garbage_frame,garbage_uid,speed=0.5):
    """Animate garbage, flying from top to bottom. Сolumn position will stay same, as specified on start."""
#TODO try finall
    try:
        uid=garbage_uid
        rows_number, cols_number = canvas.getmaxyx()
        rows_size,cols_size = get_frame_size(garbage_frame)
        column = max(column, 0)
        column = min(column, cols_number - 1)
        row = 0
        OBSTACLES.update({uid:Obstacle(0,column,rows_size,cols_size,uid)})
        while row < rows_number and uid not in OBSTACLES_IN_LAST_COLLISIONS:
            draw_frame(canvas, row, column, garbage_frame)
            await asyncio.sleep(0)
            draw_frame(canvas, row, column, garbage_frame, negative=True)
            row += speed
            OBSTACLES[uid].row=row
    finally:
        del OBSTACLES[uid]
        if uid in OBSTACLES_IN_LAST_COLLISIONS:
            OBSTACLES_IN_LAST_COLLISIONS.remove(uid)
            COROUTINES.append(explode(canvas,row+rows_size//2,column+cols_size//2))


async def fill_orbit_with_garbage(canvas):
    garbage_frames = load_frames(
        ['duck.txt', 'hubble.txt', 'lamp.txt', 'trash_large.txt', 'trash_small.txt', 'trash_xl.txt'])
    for uid in cycle((num for num in range(64000))):
        frame = choice(garbage_frames)
        column = randint(1, canvas.getmaxyx()[1] - get_frame_size(frame)[1])
        COROUTINES.append(fly_garbage(canvas, column=column, garbage_frame=frame,garbage_uid=uid))
        await sleep(randint(0, 5 // TIC_TIMEOUT))


def load_frames(filelist):
    frames = []
    for file in filelist:
        with open(os.path.join('files', file), 'r') as frame:
            frames.append(str(frame.read()))
    return frames


def get_max_sizes(frames):
    transposed_sizes = list(zip(*[get_frame_size(frame) for frame in frames]))
    return max(transposed_sizes[0]), max(transposed_sizes[1])


def draw(canvas):
    curses.curs_set(False)
    canvas.nodelay(True)
    max_row, max_col = canvas.getmaxyx()
    max_row, max_col = max_row - 1, max_col - 1
    unic_points = set()
    while len(unic_points) < COUNT_STARS:
        star_row, star_col = randint(1, max_row - 1), randint(1, max_col - 1)
        if (star_row, star_col) not in unic_points:
            COROUTINES.append(blink(canvas, star_row, star_col, symbol=choice(list('+*.:'))))
            unic_points.add((star_row, star_col))
    game_over_frame=load_frames(['game_over.txt'])[0]
    game_over_row = (max_row - get_frame_size(game_over_frame)[0])//2
    game_over_col = (max_col - get_frame_size(game_over_frame)[1])//2
    rocket_frames = load_frames(['rocket_frame_1.txt', 'rocket_frame_2.txt'])
    rocket_height, rocket_width = get_max_sizes(rocket_frames)
    rocket = {'row': (max_row - rocket_height) // 2,
              'col': (max_col - rocket_width) // 2,
              'row_speed': 0,
              'col_speed': 0,
              }

    COROUTINES.append(fly_rocket(canvas, rocket, rocket_frames))
    COROUTINES.append(fill_orbit_with_garbage(canvas))
    COROUTINES.append( show_obstacles(canvas,OBSTACLES))

    fps_time = time.time()

    while True:
        for cor in COROUTINES.copy():
            try:
                cor.send(None)
            except StopIteration:
                COROUTINES.remove(cor)
        canvas.border()
        canvas.addstr(max_row, 3, f' FPS={1 / (time.time() - fps_time+0.00000001):6.2f} ')
        fps_time = time.time()
        if GAME_OVER[0]:
            draw_frame(canvas, game_over_row, game_over_col, game_over_frame)
        canvas.refresh()
        time.sleep(TIC_TIMEOUT)
        rows_direction, columns_direction, space_pressed = read_controls(canvas)
        rocket['row_speed'], rocket['col_speed'] = update_speed(rocket['row_speed'], rocket['col_speed'],
                                                                rows_direction, columns_direction)
        rocket['row'] = min(
            max(1, rocket['row'] + rocket['row_speed']),
            max_row - rocket_height
        )
        rocket['col'] = min(
            max(1, rocket['col'] + rocket['col_speed']),
            max_col - rocket_width
        )
        if space_pressed and rocket['row'] > 2 and not GAME_OVER[0]:
            COROUTINES.append(fire(canvas, rocket['row'] - 1, rocket['col'] + 2))


if __name__ == '__main__':
    curses.update_lines_cols()
    curses.wrapper(draw)
