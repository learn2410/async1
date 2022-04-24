import asyncio
import curses
import os
import time
from itertools import cycle
from random import randint, choice

from curses_tools import draw_frame, read_controls, get_frame_size
from explosion import explode
from game_scenario import PHRASES, get_garbage_delay_tics
from obstacles import Obstacle
from physics import update_speed

TIC_TIMEOUT = 0.1
COUNT_STARS = 200
ROCKET_SPEED = 2
BULLET_SPEED = 2.5

COROUTINES = []
OBSTACLES = {}
OBSTACLES_IN_LAST_COLLISIONS = []
OBSTACLES_IN_ZERO_ROW = []
GAME_PARAMS = {
    'gameover': False,
    'have_gun': False,
    'year': 1957,
    'level': 1,
    'score': 0,
}


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
        for uid, obstale in OBSTACLES.items():
            if obstale.has_collision(round(row), round(column), round(rows_speed)):
                OBSTACLES_IN_LAST_COLLISIONS.append(uid)
                GAME_PARAMS['score'] += 1
                return
        row += rows_speed
        column += columns_speed


async def fly_rocket(canvas, position, frames):
    frame_gen = cycle(frames)
    height, width = get_max_sizes(frames)
    for frame in frame_gen:
        frame_position = position.copy()
        draw_frame(canvas, frame_position['row'], frame_position['col'], frame, False)
        await asyncio.sleep(0)
        draw_frame(canvas, frame_position['row'], frame_position['col'], frame, True)
        for uid, obstale in OBSTACLES.items():
            if obstale.has_collision(position['row'], position['col'], height, width):
                OBSTACLES_IN_LAST_COLLISIONS.append(uid)
                GAME_PARAMS['gameover'] = True
                return


async def fly_garbage(canvas, column, garbage_frame, garbage_uid, speed=0.5):
    """Animate garbage, flying from top to bottom. Сolumn position will stay same, as specified on start."""
    uid = garbage_uid
    rows_number, cols_number = canvas.getmaxyx()
    rows_size, cols_size = get_frame_size(garbage_frame)
    column = max(column, 0)
    column = min(column, cols_number - 1)
    row = 0
    try:
        OBSTACLES.update({uid: Obstacle(0, column, rows_size, cols_size, uid)})
        while row < rows_number and uid not in OBSTACLES_IN_LAST_COLLISIONS:
            draw_frame(canvas, row, column, garbage_frame)
            await asyncio.sleep(0)
            draw_frame(canvas, row, column, garbage_frame, negative=True)
            row += speed
            OBSTACLES[uid].row = row
    finally:
        del OBSTACLES[uid]
        if uid in OBSTACLES_IN_LAST_COLLISIONS:
            OBSTACLES_IN_LAST_COLLISIONS.remove(uid)
            COROUTINES.append(explode(canvas, row + rows_size // 2, column + cols_size // 2))


def get_new_garbage_column(max_column, garbage_rows, garbage_cols):
    candidates = range(max_column)
    for obstacle in OBSTACLES.values():
        if garbage_rows > obstacle.row:
            candidates = [column for column in candidates
                          if column < obstacle.column - garbage_cols
                          or column > obstacle.column + obstacle.columns_size]
    return choice(candidates) if candidates else None


async def fill_orbit_with_garbage(canvas):
    garbage_frames = load_frames(
        ['duck.txt', 'hubble.txt', 'lamp.txt', 'trash_large.txt', 'trash_small.txt', 'trash_xl.txt'])
    max_row, max_col = canvas.getmaxyx()
    for uid in cycle((num for num in range(64000))):
        delay_tics = get_garbage_delay_tics(GAME_PARAMS['year'])
        while not delay_tics:
            await sleep(1)
            delay_tics = get_garbage_delay_tics(GAME_PARAMS['year'])
        frame = choice(garbage_frames)
        height, width = get_frame_size(frame)
        column = get_new_garbage_column(max_col - width, height, width)
        if column:
            COROUTINES.append(fly_garbage(canvas, column=column, garbage_frame=frame, garbage_uid=uid))
            OBSTACLES_IN_ZERO_ROW.append(uid)
        await sleep(delay_tics)


async def year_counter():
    while True:
        await sleep(int(1.5 / TIC_TIMEOUT))
        old_garbage_delay_tics = get_garbage_delay_tics(GAME_PARAMS['year'])
        GAME_PARAMS['year'] += 1
        if get_garbage_delay_tics(GAME_PARAMS['year']) != old_garbage_delay_tics:
            GAME_PARAMS['level'] += 1
        GAME_PARAMS['have_gun'] = GAME_PARAMS['year'] >= 2020


def load_frames(filelist):
    frames = []
    for file in filelist:
        with open(os.path.join('files', file), 'r') as frame:
            frames.append(str(frame.read()))
    return frames


def get_max_sizes(frames):
    transposed_sizes = list(zip(*[get_frame_size(frame) for frame in frames]))
    return max(transposed_sizes[0]), max(transposed_sizes[1])


def draw_scoreboard(scoreboard):
    max_row, max_col = scoreboard.getmaxyx()
    scoreboard.addstr(0, 1, f'<{GAME_PARAMS["score"]:3}>')
    scoreboard.addstr(0, 7, f'<level:{GAME_PARAMS["level"]}>')
    scoreboard.addstr(0, 17, f'<year:{GAME_PARAMS["year"]}>')
    event_year = [year for year in PHRASES if year <= GAME_PARAMS["year"]][-1]
    scoreboard.addstr(0, 30, f'[{PHRASES[event_year]}]'[:max_col - 32])


def draw_game_over(canvas, game_over_frame):
    max_row, max_col = canvas.getmaxyx()
    frame_rows, frame_cols = get_frame_size(game_over_frame)
    frame_row, frame_col = (max_row - frame_rows) // 2, (max_col - frame_cols) // 2
    area = canvas.derwin(frame_rows + 3, frame_cols + 4, frame_row - 1, frame_col - 2, )
    area.clear()
    area.border()
    draw_frame(area, 1, 2, game_over_frame)


def draw(canvas):
    curses.curs_set(False)
    canvas.nodelay(True)
    max_row, max_col = canvas.getmaxyx()
    max_row, max_col = max_row - 1, max_col - 1
    scoreboard = canvas.derwin(1, max_col - 2, max_row, 1)
    unic_points = set()
    while len(unic_points) < COUNT_STARS:
        star_row, star_col = randint(1, max_row - 1), randint(1, max_col - 1)
        if (star_row, star_col) not in unic_points:
            COROUTINES.append(blink(canvas, star_row, star_col, symbol=choice(list('+*.:'))))
            unic_points.add((star_row, star_col))
    game_over_frame = load_frames(['game_over.txt'])[0]

    rocket_frames = load_frames(['rocket_frame_1.txt', 'rocket_frame_2.txt'])
    rocket_height, rocket_width = get_max_sizes(rocket_frames)
    rocket = {'row': (max_row - rocket_height) // 2,
              'col': (max_col - rocket_width) // 2,
              'row_speed': 0,
              'col_speed': 0,
              }

    COROUTINES.append(fly_rocket(canvas, rocket, rocket_frames))
    COROUTINES.append(fill_orbit_with_garbage(canvas))
    COROUTINES.append(year_counter())

    while True:
        for cor in COROUTINES.copy():
            try:
                cor.send(None)
            except StopIteration:
                COROUTINES.remove(cor)
        canvas.border()
        if GAME_PARAMS['gameover']:
            draw_game_over(canvas, game_over_frame)
        draw_scoreboard(scoreboard)
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
        if space_pressed and rocket['row'] > 2 and not GAME_PARAMS['gameover'] and GAME_PARAMS['have_gun']:
            COROUTINES.append(fire(canvas, rocket['row'] - 1, rocket['col'] + 2))


if __name__ == '__main__':
    curses.update_lines_cols()
    curses.wrapper(draw)
