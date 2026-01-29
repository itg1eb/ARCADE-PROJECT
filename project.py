"""
PLANE 1990
2D игра-аркада с самолётом в лабиринте
"""

import arcade
import random
import math
import csv
import os
import time
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

# ========== КОНСТАНТЫ ==========
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SCREEN_TITLE = "PLANE 1990"

PLAYER_SPEED = 3
ENEMY_SPEED = 1.5
BULLET_SPEED = 8
ENEMY_BULLET_SPEED = 5

PLAYER_SIZE = 20
ENEMY_SIZE = 18
BULLET_SIZE = 4
WALL_SIZE = 32

MAX_ENEMIES = 6
ENEMY_SPAWN_DELAY = 2.0
ENEMY_SHOOT_DELAY = 1.0
ENEMY_HOMING_DELAY = 1.0  # Задержка самонаведения

ANIMATION_DURATION = 0.7
SHOOT_COOLDOWN = 0.3  # КД между выстрелами
LASER_COOLDOWN = 4.0  # Время перезарядки одного выстрела
MAX_LASERS = 2  # Максимальное количество выстрелов

# Уровни игры
LEVELS = [
    {"walls": 3, "enemies": 3, "time": 30},  # Уровень 1
    {"walls": 4, "enemies": 4, "time": 40},  # Уровень 2
    {"walls": 5, "enemies": 5, "time": 50},  # Уровень 3
    {"walls": 6, "enemies": 6, "time": 60},  # Уровень 4 (финальный)
]

# Цвета
COLOR_BLUE_LIGHT = arcade.color.LIGHT_BLUE
COLOR_GREEN_DARK = arcade.color.DARK_GREEN
COLOR_RED = arcade.color.RED
COLOR_GREEN_WIN = arcade.color.GREEN  # Зеленый для WIN
COLOR_ORANGE = arcade.color.ORANGE  # Оранжевые стены
COLOR_BACKGROUND = arcade.color.BLACK  # Черный фон
COLOR_TEXT = arcade.color.WHITE
COLOR_MENU_BG = arcade.color.DARK_SLATE_GRAY
COLOR_BUTTON = arcade.color.GRAY
COLOR_COOLDOWN = arcade.color.DARK_GRAY  # Цвет для перезарядки
COLOR_READY = arcade.color.LIME  # Цвет готовного выстрела
COLOR_LEVEL = arcade.color.CYAN  # Цвет для отображения уровня


# Состояния игры
class GameState(Enum):
    MENU = 1
    RULES = 2
    READY = 3
    PLAYING = 4
    GAME_OVER = 5
    WIN = 6  # Новое состояние - победа
    LEVEL_COMPLETE = 7  # Завершение уровня
    HIGH_SCORES = 8  # Таблица рекордов


class Particle:
    """Класс для частиц эффектов"""

    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.size = random.randint(2, 6)
        self.speed_x = random.uniform(-2, 2)
        self.speed_y = random.uniform(-2, 2)
        self.life = random.uniform(0.5, 1.5)
        self.alpha = 255

    def update(self, delta_time):
        """Обновление частицы"""
        self.x += self.speed_x
        self.y += self.speed_y
        self.life -= delta_time
        self.alpha = int(255 * (self.life / 1.0))
        # Ограничиваем значение альфа-канала в диапазоне 0-255
        if self.alpha < 0:
            self.alpha = 0
        elif self.alpha > 255:
            self.alpha = 255
        return self.life > 0

    def draw(self, offset_x=0, offset_y=0):
        """Отрисовка частицы"""
        if self.alpha > 0:
            # Ограничиваем значение альфа-канала на всякий случай
            alpha = self.alpha
            if alpha < 0:
                alpha = 0
            elif alpha > 255:
                alpha = 255

            arcade.draw_circle_filled(
                self.x - offset_x,
                self.y - offset_y,
                self.size,
                (self.color[0], self.color[1], self.color[2], alpha)
            )


class ParticleSystem:
    """Система управления частицами"""

    def __init__(self):
        self.particles = []

    def add_explosion(self, x, y, color, count=20):
        """Добавить взрыв частиц"""
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def add_trail(self, x, y, color):
        """Добавить след за объектом"""
        if random.random() < 0.3:  # 30% шанс создать частицу
            self.particles.append(Particle(x, y, color))

    def update(self, delta_time):
        """Обновление всех частиц"""
        self.particles = [p for p in self.particles if p.update(delta_time)]

    def draw(self, offset_x=0, offset_y=0):
        """Отрисовка всех частиц"""
        for particle in self.particles:
            particle.draw(offset_x, offset_y)


# ========== КЛАССЫ ДЛЯ ИГРОВЫХ ОБЪЕКТОВ ==========
@dataclass
class Wall:
    """Класс для стены лабиринта"""
    x: int
    y: int
    width: int = WALL_SIZE
    height: int = WALL_SIZE

    def get_rect(self):
        """Получить прямоугольник для проверки коллизий"""
        left = self.x - self.width // 2
        right = self.x + self.width // 2
        bottom = self.y - self.height // 2
        top = self.y + self.height // 2
        return (left, right, bottom, top)

    def draw(self, offset_x=0, offset_y=0):
        """Отрисовка стены"""
        left, right, bottom, top = self.get_rect()
        arcade.draw_lrbt_rectangle_filled(
            left - offset_x,
            right - offset_x,
            bottom - offset_y,
            top - offset_y,
            COLOR_ORANGE
        )


class Bullet:
    """Класс для пуль/лазеров"""

    def __init__(self, x: float, y: float, angle: float, is_player: bool = True):
        self.x = x
        self.y = y
        self.angle = angle
        self.speed = BULLET_SPEED if is_player else ENEMY_BULLET_SPEED
        self.is_player = is_player
        self.radius = BULLET_SIZE

        # Для анимации
        self.trail_timer = 0
        self.trail_interval = 0.05

    def update(self, walls: List[Wall], particles: ParticleSystem, delta_time: float) -> bool:
        """Обновление позиции пули"""
        angle_rad = math.radians(self.angle)
        new_x = self.x + math.cos(angle_rad) * self.speed
        new_y = self.y + math.sin(angle_rad) * self.speed

        # Добавление следа
        self.trail_timer += delta_time
        if self.trail_timer >= self.trail_interval:
            self.trail_timer = 0
            trail_color = (255, 0, 0) if self.is_player else (0, 255, 0)
            particles.add_trail(self.x, self.y, trail_color)

        # Проверка столкновения со стенами
        for wall in walls:
            left, right, bottom, top = wall.get_rect()
            if (left <= new_x <= right and bottom <= new_y <= top):
                # Эффект при попадании в стену
                wall_color = (255, 165, 0)  # Оранжевый
                particles.add_explosion(new_x, new_y, wall_color, 10)
                return True  # Пуля уничтожена

        self.x = new_x
        self.y = new_y
        return False

    def is_off_screen(self) -> bool:
        """Проверка, вышла ли пуля за пределы экрана"""
        return (self.x < 0 or self.x > SCREEN_WIDTH or
                self.y < 0 or self.y > SCREEN_HEIGHT)

    def draw(self, offset_x=0, offset_y=0):
        """Отрисовка пули"""
        draw_x = self.x - offset_x
        draw_y = self.y - offset_y
        color = COLOR_RED if self.is_player else COLOR_GREEN_DARK
        arcade.draw_circle_filled(draw_x, draw_y, self.radius, color)

        # Эффект свечения для лазера игрока
        if self.is_player:
            arcade.draw_circle_outline(draw_x, draw_y, self.radius + 1, arcade.color.WHITE, 1)


class Plane:
    """Базовый класс для самолёта"""

    def __init__(self, x: float, y: float, color: arcade.color, is_player: bool = False):
        self.x = x
        self.y = y
        self.angle = 0
        self.color = color
        self.is_player = is_player
        self.speed = PLAYER_SPEED if is_player else ENEMY_SPEED
        self.size = PLAYER_SIZE if is_player else ENEMY_SIZE

        # Для анимации
        self.animation_timer = 0
        self.wing_flap = 0

        # Управление для игрока
        self.moving_up = False
        self.moving_down = False
        self.moving_left = False
        self.moving_right = False

        # Для врагов
        self.target_angle = 0
        self.direction_change_timer = 0
        self.can_see_player = False
        self.shoot_timer = ENEMY_SHOOT_DELAY  # Враги сразу могут стрелять при виде
        self.homing_timer = 0  # Таймер для самонаведения
        self.is_homing = False  # Флаг режима самонаведения
        self.last_shot_time = 0

        # Для игрока - система перезарядки лазеров
        if self.is_player:
            self.laser_count = MAX_LASERS  # Начальное количество выстрелов
            self.laser_recharge_timers = [0.0, 0.0]  # Таймеры перезарядки для каждого выстрела
            self.shoot_cooldown = 0  # КД между выстрелами
        else:
            self.shoot_cooldown = 0

    def set_movement(self, up=False, down=False, left=False, right=False):
        """Установить состояние движения (для игрока)"""
        self.moving_up = up
        self.moving_down = down
        self.moving_left = left
        self.moving_right = right

    def move(self, walls: List[Wall]):
        """Перемещение самолёта с проверкой коллизий"""
        dx = 0
        dy = 0

        if self.is_player:
            # Управление для игрока
            if self.moving_up:
                dy = 1
            if self.moving_down:
                dy = -1
            if self.moving_left:
                dx = -1
            if self.moving_right:
                dx = 1

            if dx != 0 or dy != 0:
                self.angle = math.degrees(math.atan2(dy, dx))
        else:
            # Для врагов - движение по текущему углу
            dx = 1  # Враг всегда движется вперед по своему направлению

        angle_rad = math.radians(self.angle)
        new_x = self.x + math.cos(angle_rad) * self.speed * (1 if dx != 0 or not self.is_player else 0)
        new_y = self.y + math.sin(angle_rad) * self.speed * (1 if dy != 0 or not self.is_player else 0)

        # Проверка столкновения со стенами
        can_move = True
        for wall in walls:
            left, right, bottom, top = wall.get_rect()
            # Проверяем, будет ли самолет пересекаться со стеной
            distance_x = abs(new_x - (left + right) / 2)
            distance_y = abs(new_y - (bottom + top) / 2)

            half_width = (right - left) / 2 + self.size
            half_height = (top - bottom) / 2 + self.size

            if distance_x < half_width and distance_y < half_height:
                can_move = False
                break

        # Проверка границ экрана
        if (self.size <= new_x <= SCREEN_WIDTH - self.size and
                self.size <= new_y <= SCREEN_HEIGHT - self.size and can_move):
            self.x = new_x
            self.y = new_y

    def update(self, walls: List[Wall], player=None, delta_time: float = 0.016):
        """Обновление состояния"""
        # Обновление анимации
        self.animation_timer += delta_time
        self.wing_flap = math.sin(self.animation_timer * 10) * 5

        if self.is_player:
            # Обновление КД между выстрелами
            if self.shoot_cooldown > 0:
                self.shoot_cooldown -= delta_time

            # Обновление таймеров перезарядки лазеров
            for i in range(len(self.laser_recharge_timers)):
                if self.laser_recharge_timers[i] > 0:
                    self.laser_recharge_timers[i] -= delta_time
                    if self.laser_recharge_timers[i] <= 0:
                        self.laser_recharge_timers[i] = 0
                        self.laser_count = min(self.laser_count + 1, MAX_LASERS)

        if not self.is_player:
            self._update_enemy(walls, player, delta_time)

        # Движение
        self.move(walls)

    def _update_enemy(self, walls: List[Wall], player, delta_time: float):
        """Обновление вражеского самолёта"""
        if not player:
            return

        # Таймер смены направления
        self.direction_change_timer -= delta_time

        # Проверка расстояния до игрока для самонаведения
        dx_to_player = player.x - self.x
        dy_to_player = player.y - self.y
        distance_to_player = math.sqrt(dx_to_player ** 2 + dy_to_player ** 2)

        # Если игрок близко (в радиусе 200 пикселей) - активируем самонаведение
        if distance_to_player < 200:
            if not self.is_homing:
                self.is_homing = True
                self.homing_timer = ENEMY_HOMING_DELAY

            if self.homing_timer > 0:
                self.homing_timer -= delta_time

            # После задержки в 1 секунду - поворачиваемся к игроку
            if self.homing_timer <= 0:
                # Поворот к игроку
                target_angle = math.degrees(math.atan2(dy_to_player, dx_to_player))
                angle_diff = (target_angle - self.angle) % 360
                if angle_diff > 180:
                    angle_diff -= 360

                # Быстрый поворот при самонаведении
                self.angle += angle_diff * 0.2

                # При самонаведении враг движется к игроку
                self.target_angle = target_angle
                self.direction_change_timer = 0  # Отменяем случайное движение
        else:
            # Игрок далеко - обычное поведение
            self.is_homing = False
            self.homing_timer = ENEMY_HOMING_DELAY

            if self.direction_change_timer <= 0:
                # Выбираем случайное направление (0, 90, 180, 270 градусов)
                self.target_angle = random.choice([0, 90, 180, 270])
                self.direction_change_timer = random.uniform(1, 3)

            # Плавный поворот к цели
            angle_diff = (self.target_angle - self.angle) % 360
            if angle_diff > 180:
                angle_diff -= 360

            self.angle += angle_diff * 0.05  # Медленный поворот

        # Проверка видимости игрока
        self._check_player_visibility(player, walls)

        # Обновление таймера стрельбы
        if self.shoot_timer > 0:
            self.shoot_timer -= delta_time

    def _check_player_visibility(self, player, walls: List[Wall]) -> bool:
        """Проверка, виден ли игрок врагу"""
        if not player:
            self.can_see_player = False
            return False

        # Вычисляем вектор к игроку
        dx = player.x - self.x
        dy = player.y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # Если игрок слишком далеко, не видим
        if distance > 300:
            self.can_see_player = False
            return False

        # Вычисляем угол к игроку
        angle_to_player = math.degrees(math.atan2(dy, dx))

        # Проверяем, смотрит ли враг примерно в сторону игрока (в пределах 45 градусов)
        angle_diff = abs((angle_to_player - self.angle) % 360)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff

        if angle_diff > 45:  # Если не смотрит в сторону игрока
            self.can_see_player = False
            return False

        # Проверка наличия стен между ними (лучший алгоритм)
        steps = int(distance / 10)  # Проверяем через каждые 10 пикселей
        for i in range(1, steps + 1):
            check_x = self.x + dx * i / steps
            check_y = self.y + dy * i / steps

            for wall in walls:
                left, right, bottom, top = wall.get_rect()
                if (left <= check_x <= right and bottom <= check_y <= top):
                    self.can_see_player = False
                    return False

        self.can_see_player = True
        return True

    def shoot(self) -> Optional[Bullet]:
        """Выстрел из самолёта"""
        if self.is_player:
            # Проверяем, есть ли доступные выстрелы
            if self.laser_count > 0 and self.shoot_cooldown <= 0:
                # Находим индекс заряда для перезарядки
                for i in range(len(self.laser_recharge_timers)):
                    if self.laser_recharge_timers[i] <= 0:
                        self.laser_recharge_timers[i] = LASER_COOLDOWN
                        break

                self.laser_count -= 1
                self.shoot_cooldown = SHOOT_COOLDOWN
                return Bullet(self.x, self.y, self.angle, True)
        else:
            # Враг стреляет если видит игрока или находится в режиме самонаведения
            if (self.can_see_player or self.is_homing) and self.shoot_timer <= 0:
                # При самонаведении стреляем точно в игрока
                if self.is_homing and hasattr(self, '_last_player_pos'):
                    dx = self._last_player_pos[0] - self.x
                    dy = self._last_player_pos[1] - self.y
                    shoot_angle = math.degrees(math.atan2(dy, dx))
                else:
                    shoot_angle = self.angle

                self.shoot_timer = ENEMY_SHOOT_DELAY
                return Bullet(self.x, self.y, shoot_angle, False)
        return None

    def draw(self, offset_x=0, offset_y=0):
        """Отрисовка самолёта"""
        draw_x = self.x - offset_x
        draw_y = self.y - offset_y

        # Анимация крыльев
        wing_offset = self.wing_flap

        # Отрисовка корпуса
        arcade.draw_circle_filled(draw_x, draw_y, self.size, self.color)

        # Отрисовка носа (треугольник) с анимацией
        angle_rad = math.radians(self.angle)
        nose_x = draw_x + math.cos(angle_rad) * (self.size + 5)
        nose_y = draw_y + math.sin(angle_rad) * (self.size + 5)

        # Боковые точки для треугольника с анимацией крыльев
        perp_angle = angle_rad + math.pi / 2
        wing_x1 = draw_x + math.cos(perp_angle) * (self.size / 2 + wing_offset)
        wing_y1 = draw_y + math.sin(perp_angle) * (self.size / 2 + wing_offset)
        wing_x2 = draw_x - math.cos(perp_angle) * (self.size / 2 + wing_offset)
        wing_y2 = draw_y - math.sin(perp_angle) * (self.size / 2 + wing_offset)

        # Рисуем треугольник (нос самолёта)
        points = [
            (nose_x, nose_y),
            (wing_x1, wing_y1),
            (wing_x2, wing_y2)
        ]
        arcade.draw_polygon_filled(points, self.color)

        # Для врагов: отображение состояния
        if not self.is_player:
            if self.can_see_player:
                # Красный контур если видит игрока
                arcade.draw_circle_outline(draw_x, draw_y, self.size + 5, COLOR_RED, 2)
            elif self.is_homing:
                # Желтый контур если в режиме самонаведения
                arcade.draw_circle_outline(draw_x, draw_y, self.size + 8, arcade.color.YELLOW, 2)


# ========== КЛАСС ДЛЯ КНОПОК ==========
class Button:
    """Класс для кнопок меню"""

    def __init__(self, x: float, y: float, width: float, height: float,
                 text: str, text_size: int = 20, color=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.text = text
        self.text_size = text_size
        self.color = color or COLOR_BUTTON
        self.text_color = COLOR_TEXT
        self.hover = False

    def is_clicked(self, click_x: float, click_y: float) -> bool:
        """Проверка, нажата ли кнопка"""
        left = self.x - self.width / 2
        right = self.x + self.width / 2
        bottom = self.y - self.height / 2
        top = self.y + self.height / 2

        self.hover = (left <= click_x <= right and bottom <= click_y <= top)
        return self.hover

    def draw(self):
        """Отрисовка кнопки с эффектом наведения"""
        # Отрисовка фона кнопки
        left = self.x - self.width / 2
        right = self.x + self.width / 2
        bottom = self.y - self.height / 2
        top = self.y + self.height / 2

        # Эффект при наведении
        button_color = self.color
        if self.hover:
            # Осветляем цвет при наведении
            button_color = (
                min(255, int(self.color[0] * 1.2)),
                min(255, int(self.color[1] * 1.2)),
                min(255, int(self.color[2] * 1.2))
            )

        arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, button_color)
        arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, COLOR_TEXT, 2)

        # Отрисовка текста
        arcade.draw_text(self.text, self.x, self.y,
                         self.text_color, self.text_size,
                         anchor_x="center", anchor_y="center",
                         font_name="Arial", bold=True)


# ========== СИСТЕМА ХРАНЕНИЯ ДАННЫХ ==========
class HighScoreManager:
    """Менеджер таблицы рекордов"""

    def __init__(self, filename="highscores.csv"):
        self.filename = filename
        self.scores = []
        self.load_scores()

    def load_scores(self):
        """Загрузка рекордов из файла"""
        self.scores = []
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', newline='', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    for row in reader:
                        if len(row) >= 4:
                            name, score, level, date = row[:4]
                            self.scores.append({
                                'name': name,
                                'score': int(score),
                                'level': int(level),
                                'date': date
                            })
            except Exception as e:
                print(f"Ошибка загрузки рекордов: {e}")
                self.scores = []

        # Сортировка по очкам
        self.scores.sort(key=lambda x: x['score'], reverse=True)
        # Оставляем только топ-10
        self.scores = self.scores[:10]

    def save_scores(self):
        """Сохранение рекордов в файл"""
        try:
            with open(self.filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                for score in self.scores:
                    writer.writerow([score['name'], score['score'], score['level'], score['date']])
        except Exception as e:
            print(f"Ошибка сохранения рекордов: {e}")

    def add_score(self, name, score, level):
        """Добавление нового рекорда"""
        self.scores.append({
            'name': name,
            'score': score,
            'level': level,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        self.scores.sort(key=lambda x: x['score'], reverse=True)
        self.scores = self.scores[:10]
        self.save_scores()

    def get_top_scores(self, count=10):
        """Получение топовых рекордов"""
        return self.scores[:count]


# ========== КАМЕРА ==========
class Camera:
    """Класс камеры для следования за игроком"""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.shake_timer = 0
        self.shake_intensity = 0
        self.offset_x = 0
        self.offset_y = 0
        self.target_x = 0
        self.target_y = 0

    def update(self, player, delta_time):
        """Обновление камеры"""
        # Дрожание камеры
        if self.shake_timer > 0:
            self.shake_timer -= delta_time
            self.shake_intensity = max(0, self.shake_intensity - delta_time * 10)
        else:
            self.shake_intensity = 0

        # Позиция камеры с учетом дрожания
        if player:
            self.target_x = player.x - self.width / 2
            self.target_y = player.y - self.height / 2

            # Добавляем дрожание
            if self.shake_intensity > 0:
                self.target_x += random.uniform(-self.shake_intensity, self.shake_intensity)
                self.target_y += random.uniform(-self.shake_intensity, self.shake_intensity)

            # Ограничиваем камеру границами уровня
            self.target_x = max(0, min(self.target_x, SCREEN_WIDTH * 2 - self.width))
            self.target_y = max(0, min(self.target_y, SCREEN_HEIGHT * 2 - self.height))

            # Плавное перемещение камеры к цели
            self.offset_x += (self.target_x - self.offset_x) * 0.1
            self.offset_y += (self.target_y - self.offset_y) * 0.1

    def shake(self, intensity=10, duration=0.3):
        """Запуск дрожания камеры"""
        self.shake_timer = duration
        self.shake_intensity = intensity


# ========== ГЛАВНЫЙ КЛАСС ИГРЫ ==========
class Plane1990(arcade.Window):
    """Главный класс игры"""

    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)

        # Состояние игры
        self.state = GameState.MENU
        self.animation_timer = 0

        # Игровые объекты
        self.walls: List[Wall] = []
        self.player: Optional[Plane] = None
        self.enemies: List[Plane] = []
        self.bullets: List[Bullet] = []
        self.enemy_bullets: List[Bullet] = []

        # Системы
        self.particle_system = ParticleSystem()
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.high_score_manager = HighScoreManager()

        # Игровые параметры
        self.current_level = 0
        self.score = 0
        self.enemies_killed = 0
        self.time_survived = 0
        self.player_name = "Игрок"
        self.name_input_active = False
        self.name_input = ""

        # Список свободных мест для спавна (черные области)
        self.free_spawn_areas: List[tuple] = []

        # Таймеры
        self.enemy_spawn_timer = ENEMY_SPAWN_DELAY
        self.game_start_timer = 0
        self.game_time = 0  # Таймер игры в секундах
        self.win_time = 60  # Время для победы: 60 секунд
        self.level_start_time = 0

        # UI элементы (кнопки)
        self.button_start = None
        self.button_continue = None
        self.button_restart = None
        self.button_menu = None
        self.button_win_restart = None  # Кнопка для экрана победы
        self.button_win_menu = None  # Кнопка для экрана победы
        self.button_next_level = None  # Кнопка следующего уровня
        self.button_high_scores = None  # Кнопка таблицы рекордов
        self.button_back_to_menu = None  # Кнопка назад в меню

        # Управление стрельбой
        self.is_shooting = False
        self.last_shoot_time = 0

        # Звуки (заглушки)
        self.sound_enabled = True

        # Инициализация
        arcade.set_background_color(COLOR_BACKGROUND)
        self.setup()

    def setup(self):
        """Настройка игры"""
        # Создание случайного лабиринта для текущего уровня
        self._create_level_maze()

        # Определяем свободные области для спавна
        self._calculate_free_areas()

        # Создание игрока в центре свободной области
        player_spawn = self._find_valid_spawn_position(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.player = Plane(player_spawn[0], player_spawn[1],
                            COLOR_BLUE_LIGHT, True)

        # Очистка врагов и пуль
        self.enemies.clear()
        self.bullets.clear()
        self.enemy_bullets.clear()
        self.particle_system = ParticleSystem()

        # Сброс таймеров
        self.enemy_spawn_timer = ENEMY_SPAWN_DELAY
        self.game_time = 0  # Сброс таймера игры
        self.level_start_time = 0
        self.is_shooting = False
        self.enemies_killed = 0

        # Создание UI элементов (кнопки)
        self._create_ui_elements()

    def _create_level_maze(self):
        """Создание лабиринта для текущего уровня"""
        self.walls.clear()

        # Внешние стены (границы)
        for x in range(WALL_SIZE // 2, SCREEN_WIDTH - WALL_SIZE // 2 + 1, WALL_SIZE):
            self.walls.append(Wall(x, WALL_SIZE // 2))
            self.walls.append(Wall(x, SCREEN_HEIGHT - WALL_SIZE // 2))

        for y in range(WALL_SIZE // 2, SCREEN_HEIGHT - WALL_SIZE // 2 + 1, WALL_SIZE):
            self.walls.append(Wall(WALL_SIZE // 2, y))
            self.walls.append(Wall(SCREEN_WIDTH - WALL_SIZE // 2, y))

        # Получаем параметры текущего уровня
        if self.current_level < len(LEVELS):
            level_params = LEVELS[self.current_level]
            wall_count = level_params["walls"]
        else:
            # Если уровни закончились, используем максимальные значения
            wall_count = 6

        # Создаем случайные стенки для уровня
        for _ in range(wall_count):
            # Случайный размер стенки (1-3 блока в ширину и высоту)
            width_blocks = random.randint(1, 3)
            height_blocks = random.randint(1, 3)

            # Случайная позиция, но не слишком близко к краям
            min_x = WALL_SIZE * 3
            max_x = SCREEN_WIDTH - WALL_SIZE * 3 - width_blocks * WALL_SIZE
            min_y = WALL_SIZE * 3
            max_y = SCREEN_HEIGHT - WALL_SIZE * 3 - height_blocks * WALL_SIZE

            if max_x > min_x and max_y > min_y:
                start_x = random.randint(min_x, max_x)
                start_y = random.randint(min_y, max_y)

                # Создаем стенку из блоков
                for i in range(width_blocks):
                    for j in range(height_blocks):
                        wall_x = start_x + i * WALL_SIZE
                        wall_y = start_y + j * WALL_SIZE

                        # Проверяем, чтобы стенка не перекрывала центр
                        center_distance = math.sqrt((wall_x - SCREEN_WIDTH // 2) ** 2 +
                                                    (wall_y - SCREEN_HEIGHT // 2) ** 2)
                        if center_distance > 150:  # Не слишком близко к центру
                            self.walls.append(Wall(wall_x, wall_y))

    def _calculate_free_areas(self):
        """Вычисление свободных областей (черных) для спавна"""
        self.free_spawn_areas.clear()

        # Разделяем экран на сетку
        grid_size = 50
        for x in range(grid_size // 2, SCREEN_WIDTH, grid_size):
            for y in range(grid_size // 2, SCREEN_HEIGHT, grid_size):
                is_free = True

                # Проверяем, не попадает ли точка в стену
                for wall in self.walls:
                    left, right, bottom, top = wall.get_rect()
                    if left <= x <= right and bottom <= y <= top:
                        is_free = False
                        break

                # Проверяем границы от стен
                if is_free:
                    # Проверяем, достаточно ли места от стен
                    min_distance = PLAYER_SIZE * 2
                    too_close_to_wall = False

                    for wall in self.walls:
                        wall_center_x = (wall.get_rect()[0] + wall.get_rect()[1]) / 2
                        wall_center_y = (wall.get_rect()[2] + wall.get_rect()[3]) / 2
                        distance = math.sqrt((x - wall_center_x) ** 2 + (y - wall_center_y) ** 2)

                        if distance < min_distance:
                            too_close_to_wall = True
                            break

                    if not too_close_to_wall:
                        self.free_spawn_areas.append((x, y))

    def _find_valid_spawn_position(self, preferred_x, preferred_y):
        """Найти валидную позицию для спавна"""
        # Сначала пытаемся использовать предпочитаемую позицию
        if self._is_position_free(preferred_x, preferred_y):
            return (preferred_x, preferred_y)

        # Ищем ближайшую свободную позицию
        best_pos = None
        best_distance = float('inf')

        for pos in self.free_spawn_areas:
            distance = math.sqrt((pos[0] - preferred_x) ** 2 + (pos[1] - preferred_y) ** 2)
            if distance < best_distance and self._is_position_free(pos[0], pos[1]):
                best_distance = distance
                best_pos = pos

        # Если не нашли, используем первую свободную
        if best_pos is None and self.free_spawn_areas:
            best_pos = self.free_spawn_areas[0]

        return best_pos or (preferred_x, preferred_y)

    def _is_position_free(self, x, y):
        """Проверяет, свободна ли позиция от стен"""
        for wall in self.walls:
            left, right, bottom, top = wall.get_rect()
            # Проверяем с запасом в размер самолета
            if (left - PLAYER_SIZE <= x <= right + PLAYER_SIZE and
                    bottom - PLAYER_SIZE <= y <= top + PLAYER_SIZE):
                return False
        return True

    def _is_position_far_from_other_enemies(self, x, y, min_distance=150):
        """Проверяет, достаточно ли далеко позиция от других врагов"""
        for enemy in self.enemies:
            distance = math.sqrt((x - enemy.x) ** 2 + (y - enemy.y) ** 2)
            if distance < min_distance:
                return False
        return True

    def _create_ui_elements(self):
        """Создание UI элементов"""
        # Кнопка "Начать игру"
        self.button_start = Button(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50,
                                   200, 50, "НАЧАТЬ ИГРУ", 24)

        # Кнопка "Продолжить"
        self.button_continue = Button(SCREEN_WIDTH // 2, 100,
                                      200, 50, "ПРОДОЛЖИТЬ", 24)

        # Кнопки для Game Over
        self.button_restart = Button(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50,
                                     200, 40, "ЗАНОВО", 22)

        self.button_menu = Button(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 120,
                                  200, 40, "В ГЛАВНОЕ МЕНЮ", 18)

        # Кнопки для экрана победы
        self.button_win_restart = Button(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50,
                                         200, 40, "ЗАНОВО", 22)

        self.button_win_menu = Button(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 120,
                                      200, 40, "В ГЛАВНОЕ МЕНЮ", 18)

        # Кнопка следующего уровня
        self.button_next_level = Button(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50,
                                        200, 40, "СЛЕДУЮЩИЙ УРОВЕНЬ", 20)

        # Кнопка таблицы рекордов
        self.button_high_scores = Button(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 120,
                                         200, 40, "ТАБЛИЦА РЕКОРДОВ", 18)

        # Кнопка назад в меню
        self.button_back_to_menu = Button(SCREEN_WIDTH // 2, 80,
                                          200, 40, "В ГЛАВНОЕ МЕНЮ", 18)

    def on_draw(self):
        """Отрисовка игры"""
        self.clear(COLOR_BACKGROUND)  # Черный фон

        if self.state == GameState.MENU:
            self._draw_menu()
        elif self.state == GameState.RULES:
            self._draw_rules()
        elif self.state == GameState.READY:
            self._draw_ready()
        elif self.state == GameState.PLAYING:
            self._draw_game()
        elif self.state == GameState.GAME_OVER:
            self._draw_game_over()
        elif self.state == GameState.WIN:
            self._draw_win()
        elif self.state == GameState.LEVEL_COMPLETE:
            self._draw_level_complete()
        elif self.state == GameState.HIGH_SCORES:
            self._draw_high_scores()

    def _draw_menu(self):
        """Отрисовка главного меню"""
        # Анимация фона - летающие частицы
        self.particle_system.draw()

        # Заголовок с анимацией
        title_y = SCREEN_HEIGHT - 150 + math.sin(time.time() * 2) * 5
        arcade.draw_text("PLANE 1990", SCREEN_WIDTH // 2, title_y,
                         COLOR_TEXT, 48, anchor_x="center", anchor_y="center",
                         font_name="Garamond", bold=True)

        # Подзаголовок
        arcade.draw_text("Аркадный симулятор полета", SCREEN_WIDTH // 2, title_y - 60,
                         COLOR_TEXT, 20, anchor_x="center", anchor_y="center")

        # Кнопка "Начать игру"
        self.button_start.draw()

        # Кнопка "Таблица рекордов"
        self.button_high_scores.draw()

        # Информация о версии
        arcade.draw_text("Версия 1.0", SCREEN_WIDTH - 10, 10,
                         COLOR_TEXT, 12, anchor_x="right")

    def _draw_rules(self):
        """Отрисовка экрана с правилами"""
        # Полупрозрачный фон
        arcade.draw_lrbt_rectangle_filled(50, SCREEN_WIDTH - 50,
                                          50, SCREEN_HEIGHT - 50,
                                          (50, 50, 50, 200))  # Темно-серый полупрозрачный

        # Заголовок
        arcade.draw_text("ПРАВИЛА ИГРЫ", SCREEN_WIDTH // 2, SCREEN_HEIGHT - 100,
                         COLOR_TEXT, 36, anchor_x="center", anchor_y="center",
                         bold=True)

        # Правила
        rules = [
            "Управление самолётом: W, A, S, D (удерживать)",
            "Стрельба: Левая кнопка мыши (удерживать)",
            f"Уровней: {len(LEVELS)}, цель - пройти все",
            f"Лазеров: {MAX_LASERS}, перезарядка: {LASER_COOLDOWN}с",
            "Карта генерируется случайно для каждого уровня",
            "Враги появляются далеко друг от друга",
            "Враги самонаводятся при близости",
            "Уничтожайте врагов для получения очков",
            "Избегайте врагов и их пуль"
        ]

        for i, rule in enumerate(rules):
            y = SCREEN_HEIGHT - 180 - i * 35
            arcade.draw_text(rule, SCREEN_WIDTH // 2, y,
                             COLOR_TEXT, 18, anchor_x="center", anchor_y="center")

        # Кнопка "Продолжить"
        self.button_continue.draw()

    def _draw_ready(self):
        """Отрисовка экрана готовности"""
        # Получаем смещение камеры
        offset_x = self.camera.offset_x
        offset_y = self.camera.offset_y

        # Отрисовка игровых элементов со смещением
        for wall in self.walls:
            wall.draw(offset_x, offset_y)

        if self.player:
            self.player.draw(offset_x, offset_y)

        for enemy in self.enemies:
            enemy.draw(offset_x, offset_y)

        for bullet in self.bullets:
            bullet.draw(offset_x, offset_y)

        for bullet in self.enemy_bullets:
            bullet.draw(offset_x, offset_y)

        # Отрисовка системы частиц
        self.particle_system.draw(offset_x, offset_y)

        # Полупрозрачный фон для текста (без смещения)
        arcade.draw_lrbt_rectangle_filled(SCREEN_WIDTH // 2 - 200, SCREEN_WIDTH // 2 + 200,
                                          SCREEN_HEIGHT // 2 - 50, SCREEN_HEIGHT // 2 + 50,
                                          (50, 50, 50, 150))

        # Текст начала игры (без смещения)
        level_text = f"Уровень {self.current_level + 1}"
        arcade.draw_text(level_text, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30,
                         COLOR_LEVEL, 32, anchor_x="center", anchor_y="center", bold=True)

        arcade.draw_text("Начать игру - R", SCREEN_WIDTH // 2,
                         SCREEN_HEIGHT // 2 - 30, COLOR_TEXT, 28,
                         anchor_x="center", anchor_y="center", bold=True)

    def _draw_game(self):
        """Отрисовка игрового процесса"""
        # Получаем смещение камеры
        offset_x = self.camera.offset_x
        offset_y = self.camera.offset_y

        # Отрисовка игровых элементов со смещением
        for wall in self.walls:
            wall.draw(offset_x, offset_y)

        if self.player:
            self.player.draw(offset_x, offset_y)

        for enemy in self.enemies:
            enemy.draw(offset_x, offset_y)

        for bullet in self.bullets:
            bullet.draw(offset_x, offset_y)

        for bullet in self.enemy_bullets:
            bullet.draw(offset_x, offset_y)

        # Отрисовка системы частиц
        self.particle_system.draw(offset_x, offset_y)

        # GUI элементы (без смещения)
        # Счётчик врагов
        arcade.draw_text(f"Врагов: {len(self.enemies)}/{LEVELS[self.current_level]['enemies']}", 10,
                         SCREEN_HEIGHT - 30, COLOR_TEXT, 16)

        # Таймер игры
        time_left = max(0, LEVELS[self.current_level]['time'] - self.game_time)
        minutes = int(time_left) // 60
        seconds = int(time_left) % 60
        timer_text = f"Время: {minutes:02d}:{seconds:02d}"
        arcade.draw_text(timer_text, SCREEN_WIDTH - 150, SCREEN_HEIGHT - 30, COLOR_TEXT, 16)

        # Подсказка управления
        arcade.draw_text("Стрельба: ЛКМ | Движение: WASD", 10, 30, COLOR_TEXT, 16)

        # Отображение индикатора лазеров
        self._draw_laser_indicator()

        # Отображение счета и уровня
        arcade.draw_text(f"Очки: {self.score}", SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT - 30,
                         COLOR_TEXT, 16, anchor_x="center")
        arcade.draw_text(f"Уровень: {self.current_level + 1}/{len(LEVELS)}",
                         SCREEN_WIDTH // 2 + 100, SCREEN_HEIGHT - 30,
                         COLOR_TEXT, 16, anchor_x="center")

        # Индикатор самонаведения врагов (со смещением)
        for enemy in self.enemies:
            if enemy.is_homing:
                draw_x = enemy.x - offset_x
                draw_y = enemy.y - offset_y
                arcade.draw_text("!", draw_x + 15, draw_y + 15,
                                 arcade.color.YELLOW, 16, bold=True)

    def _draw_laser_indicator(self):
        """Отрисовка индикатора лазеров"""
        if not self.player:
            return

        # Позиция для отображения индикатора
        indicator_x = 100
        indicator_y = SCREEN_HEIGHT - 60
        circle_radius = 12
        circle_spacing = 40

        # Отображение доступных лазеров
        for i in range(MAX_LASERS):
            x = indicator_x + i * circle_spacing
            y = indicator_y

            if i < self.player.laser_count:
                # Доступный выстрел - зеленый
                arcade.draw_circle_filled(x, y, circle_radius, COLOR_READY)
                arcade.draw_circle_outline(x, y, circle_radius, COLOR_TEXT, 2)
                arcade.draw_text(str(i + 1), x, y, COLOR_BACKGROUND, 14,
                                 anchor_x="center", anchor_y="center", bold=True)
            else:
                # Перезарядка - серый с процентом
                recharge_time = self.player.laser_recharge_timers[i]
                if recharge_time > 0:
                    # Серый круг для перезарядки
                    arcade.draw_circle_filled(x, y, circle_radius, COLOR_COOLDOWN)
                    arcade.draw_circle_outline(x, y, circle_radius, COLOR_TEXT, 2)

                    # Процент перезарядки
                    percent = 100 - int((recharge_time / LASER_COOLDOWN) * 100)
                    arcade.draw_text(f"{percent}%", x, y, COLOR_TEXT, 10,
                                     anchor_x="center", anchor_y="center")
                else:
                    # Готов к перезарядке
                    arcade.draw_circle_filled(x, y, circle_radius, COLOR_COOLDOWN)
                    arcade.draw_circle_outline(x, y, circle_radius, COLOR_TEXT, 2)

        # Текст индикатора
        arcade.draw_text("ЛАЗЕРЫ:", indicator_x - 70, indicator_y,
                         COLOR_TEXT, 14, anchor_x="right", anchor_y="center")

    def _draw_game_over(self):
        """Отрисовка экрана Game Over"""
        # Получаем смещение камеры
        offset_x = self.camera.offset_x
        offset_y = self.camera.offset_y

        # Отрисовка игровых элементов со смещением
        for wall in self.walls:
            wall.draw(offset_x, offset_y)

        if self.player:
            self.player.draw(offset_x, offset_y)

        for enemy in self.enemies:
            enemy.draw(offset_x, offset_y)

        for bullet in self.bullets:
            bullet.draw(offset_x, offset_y)

        for bullet in self.enemy_bullets:
            bullet.draw(offset_x, offset_y)

        # Отрисовка системы частиц
        self.particle_system.draw(offset_x, offset_y)

        # Полупрозрачный фон (без смещения)
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT,
                                          (0, 0, 0, 150))

        # Текст Game Over (без смещения)
        arcade.draw_text("GAME OVER", SCREEN_WIDTH // 2,
                         SCREEN_HEIGHT // 2 + 150, COLOR_RED, 64,
                         anchor_x="center", anchor_y="center", bold=True)

        # Статистика (без смещения)
        stats = [
            f"Уровень: {self.current_level + 1}",
            f"Уничтожено врагов: {self.enemies_killed}",
            f"Очки: {self.score}",
            f"Время выживания: {int(self.game_time)}с"
        ]

        for i, stat in enumerate(stats):
            y = SCREEN_HEIGHT // 2 + 50 - i * 40
            arcade.draw_text(stat, SCREEN_WIDTH // 2, y,
                             COLOR_TEXT, 24, anchor_x="center", anchor_y="center")

        # Кнопки (без смещения)
        self.button_restart.draw()
        self.button_menu.draw()

    def _draw_win(self):
        """Отрисовка экрана победы"""
        # Получаем смещение камеры
        offset_x = self.camera.offset_x
        offset_y = self.camera.offset_y

        # Отрисовка игровых элементов со смещением
        for wall in self.walls:
            wall.draw(offset_x, offset_y)

        if self.player:
            self.player.draw(offset_x, offset_y)

        for enemy in self.enemies:
            enemy.draw(offset_x, offset_y)

        for bullet in self.bullets:
            bullet.draw(offset_x, offset_y)

        for bullet in self.enemy_bullets:
            bullet.draw(offset_x, offset_y)

        # Добавляем эффект победы
        for _ in range(5):
            x = random.randint(0, SCREEN_WIDTH)
            y = random.randint(0, SCREEN_HEIGHT)
            self.particle_system.add_explosion(x, y, (0, 255, 0), 10)
        self.particle_system.draw(offset_x, offset_y)

        # Полупрозрачный фон (без смещения)
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT,
                                          (0, 0, 0, 150))

        # Текст WIN зелеными буквами (без смещения)
        arcade.draw_text("ПОБЕДА!", SCREEN_WIDTH // 2,
                         SCREEN_HEIGHT // 2 + 150, COLOR_GREEN_WIN, 64,
                         anchor_x="center", anchor_y="center", bold=True)

        # Сообщение о победе (без смещения)
        arcade.draw_text("Вы прошли все уровни!", SCREEN_WIDTH // 2,
                         SCREEN_HEIGHT // 2 + 80, COLOR_TEXT, 28,
                         anchor_x="center", anchor_y="center", bold=True)

        # Финальная статистика (без смещения)
        stats = [
            f"Всего очков: {self.score}",
            f"Уничтожено врагов: {self.enemies_killed}",
            f"Пройдено уровней: {len(LEVELS)}",
            f"Общее время: {int(self.time_survived)}с"
        ]

        for i, stat in enumerate(stats):
            y = SCREEN_HEIGHT // 2 + 20 - i * 40
            arcade.draw_text(stat, SCREEN_WIDTH // 2, y,
                             COLOR_TEXT, 24, anchor_x="center", anchor_y="center")

        # Ввод имени для таблицы рекордов (без смещения)
        if self.name_input_active:
            arcade.draw_text("Введите ваше имя:", SCREEN_WIDTH // 2,
                             SCREEN_HEIGHT // 2 - 100, COLOR_TEXT, 24,
                             anchor_x="center", anchor_y="center")

            arcade.draw_rectangle_outline(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 150,
                                          300, 40, COLOR_TEXT, 2)
            arcade.draw_text(self.name_input or "_", SCREEN_WIDTH // 2,
                             SCREEN_HEIGHT // 2 - 150, COLOR_TEXT, 24,
                             anchor_x="center", anchor_y="center")

            arcade.draw_text("Нажмите Enter для сохранения", SCREEN_WIDTH // 2,
                             SCREEN_HEIGHT // 2 - 200, arcade.color.LIGHT_GRAY, 18,
                             anchor_x="center", anchor_y="center")
        else:
            # Кнопки (без смещения)
            self.button_win_restart.draw()
            self.button_win_menu.draw()
            self.button_high_scores.draw()

    def _draw_level_complete(self):
        """Отрисовка экрана завершения уровня"""
        # Получаем смещение камеры
        offset_x = self.camera.offset_x
        offset_y = self.camera.offset_y

        # Отрисовка игровых элементов со смещением
        for wall in self.walls:
            wall.draw(offset_x, offset_y)

        if self.player:
            self.player.draw(offset_x, offset_y)

        for enemy in self.enemies:
            enemy.draw(offset_x, offset_y)

        for bullet in self.bullets:
            bullet.draw(offset_x, offset_y)

        for bullet in self.enemy_bullets:
            bullet.draw(offset_x, offset_y)

        # Добавляем эффект завершения уровня
        if self.player:
            self.particle_system.add_explosion(self.player.x, self.player.y,
                                               (0, 255, 255), 15)
        self.particle_system.draw(offset_x, offset_y)

        # Полупрозрачный фон (без смещения)
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT,
                                          (0, 0, 0, 150))

        # Текст завершения уровня (без смещения)
        arcade.draw_text(f"УРОВЕНЬ {self.current_level + 1} ПРОЙДЕН!",
                         SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 150,
                         COLOR_LEVEL, 48, anchor_x="center", anchor_y="center", bold=True)

        # Статистика уровня (без смещения)
        time_taken = self.game_time - self.level_start_time
        level_score = self.enemies_killed * 100 + int(LEVELS[self.current_level]['time'] - time_taken) * 10

        stats = [
            f"Время уровня: {int(time_taken)}с",
            f"Уничтожено врагов: {self.enemies_killed}",
            f"Очки за уровень: {level_score}",
            f"Всего очков: {self.score}"
        ]

        for i, stat in enumerate(stats):
            y = SCREEN_HEIGHT // 2 + 50 - i * 40
            arcade.draw_text(stat, SCREEN_WIDTH // 2, y,
                             COLOR_TEXT, 24, anchor_x="center", anchor_y="center")

        # Кнопки (без смещения)
        if self.current_level + 1 < len(LEVELS):
            self.button_next_level.draw()
        else:
            arcade.draw_text("Это был последний уровень!", SCREEN_WIDTH // 2,
                             SCREEN_HEIGHT // 2 - 100, COLOR_TEXT, 28,
                             anchor_x="center", anchor_y="center", bold=True)
            self.button_win_menu.center_y = SCREEN_HEIGHT // 2 - 150
            self.button_win_menu.draw()
            self.button_win_menu.center_y = SCREEN_HEIGHT // 2 - 120  # Возвращаем на место

        self.button_menu.center_y = SCREEN_HEIGHT // 2 - 180
        self.button_menu.draw()
        self.button_menu.center_y = SCREEN_HEIGHT // 2 - 120  # Возвращаем на место

    def _draw_high_scores(self):
        """Отрисовка таблицы рекордов"""
        # Полупрозрачный фон
        arcade.draw_lrbt_rectangle_filled(50, SCREEN_WIDTH - 50,
                                          50, SCREEN_HEIGHT - 50,
                                          (50, 50, 50, 200))

        # Заголовок
        arcade.draw_text("ТАБЛИЦА РЕКОРДОВ", SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80,
                         COLOR_TEXT, 36, anchor_x="center", anchor_y="center", bold=True)

        # Заголовки столбцов
        arcade.draw_text("Место", 100, SCREEN_HEIGHT - 140,
                         COLOR_TEXT, 20, anchor_x="center", anchor_y="center", bold=True)
        arcade.draw_text("Имя", 250, SCREEN_HEIGHT - 140,
                         COLOR_TEXT, 20, anchor_x="center", anchor_y="center", bold=True)
        arcade.draw_text("Очки", 400, SCREEN_WIDTH // 2 + 50,
                         COLOR_TEXT, 20, anchor_x="center", anchor_y="center", bold=True)
        arcade.draw_text("Уровень", 550, SCREEN_HEIGHT - 140,
                         COLOR_TEXT, 20, anchor_x="center", anchor_y="center", bold=True)
        arcade.draw_text("Дата", 700, SCREEN_HEIGHT - 140,
                         COLOR_TEXT, 20, anchor_x="center", anchor_y="center", bold=True)

        # Линия под заголовками
        arcade.draw_line(50, SCREEN_HEIGHT - 160, SCREEN_WIDTH - 50, SCREEN_HEIGHT - 160,
                         COLOR_TEXT, 2)

        # Список рекордов
        scores = self.high_score_manager.get_top_scores(10)
        for i, score in enumerate(scores):
            y = SCREEN_HEIGHT - 200 - i * 40

            # Цвет для топ-3
            if i == 0:
                row_color = arcade.color.GOLD
            elif i == 1:
                row_color = arcade.color.SILVER
            elif i == 2:
                row_color = arcade.color.BRONZE
            else:
                row_color = COLOR_TEXT

            arcade.draw_text(f"{i + 1}.", 100, y, row_color, 18, anchor_x="center", anchor_y="center")
            arcade.draw_text(score['name'], 250, y, row_color, 18, anchor_x="center", anchor_y="center")
            arcade.draw_text(str(score['score']), 400, y, row_color, 18, anchor_x="center", anchor_y="center")
            arcade.draw_text(str(score['level']), 550, y, row_color, 18, anchor_x="center", anchor_y="center")
            arcade.draw_text(score['date'], 700, y, row_color, 16, anchor_x="center", anchor_y="center")

        # Если рекордов нет
        if not scores:
            arcade.draw_text("Пока нет рекордов. Будьте первым!",
                             SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2,
                             COLOR_TEXT, 24, anchor_x="center", anchor_y="center")

        # Кнопка "Назад в меню"
        self.button_back_to_menu.draw()

    def on_update(self, delta_time: float):
        """Обновление игры"""
        # Обновление системы частиц
        self.particle_system.update(delta_time)

        # Обновление камеры
        if self.player:
            self.camera.update(self.player, delta_time)

        if self.state == GameState.PLAYING:
            self._update_game(delta_time)

        # Обработка анимаций
        if self.animation_timer > 0:
            self.animation_timer -= delta_time

    def _update_game(self, delta_time: float):
        """Обновление игрового процесса"""
        # Обновление таймера игры
        self.game_time += delta_time
        self.time_survived += delta_time

        # Получаем параметры текущего уровня
        if self.current_level < len(LEVELS):
            level_params = LEVELS[self.current_level]
            level_time = level_params["time"]
            target_enemies = level_params["enemies"]
        else:
            level_time = 60
            target_enemies = MAX_ENEMIES

        # Проверка завершения уровня (по времени)
        if self.game_time - self.level_start_time >= level_time:
            # Начисляем очки за выживание
            self.score += int(level_time) * 10
            self.state = GameState.LEVEL_COMPLETE
            self.animation_timer = ANIMATION_DURATION
            return

        # Обновление игрока
        if self.player:
            self.player.update(self.walls, None, delta_time)

            # Автоматическая стрельба при удержании ЛКМ
            if self.is_shooting and self.player.laser_count > 0:
                bullet = self.player.shoot()
                if bullet:
                    self.bullets.append(bullet)

                    # Эффект при выстреле
                    self.particle_system.add_explosion(self.player.x, self.player.y,
                                                       (255, 255, 0), 5)
                    self.camera.shake(3, 0.1)

        # Обновление врагов
        for enemy in self.enemies[:]:
            enemy.update(self.walls, self.player, delta_time)

            # Запоминаем позицию игрока для прицеливания
            if self.player:
                enemy._last_player_pos = (self.player.x, self.player.y)

            # Выстрел врага
            bullet = enemy.shoot()
            if bullet and not enemy.is_player:
                self.enemy_bullets.append(bullet)

        # Обновление пуль игрока
        for bullet in self.bullets[:]:
            destroyed = bullet.update(self.walls, self.particle_system, delta_time)
            if destroyed or bullet.is_off_screen():
                self.bullets.remove(bullet)

        # Обновление пуль врагов
        for bullet in self.enemy_bullets[:]:
            destroyed = bullet.update(self.walls, self.particle_system, delta_time)
            if destroyed or bullet.is_off_screen():
                self.enemy_bullets.remove(bullet)

        # Спавн врагов
        self._spawn_enemies(delta_time, target_enemies)

        # Проверка столкновений
        self._check_collisions()

    def _spawn_enemies(self, delta_time: float, target_enemies: int):
        """Спавн вражеских самолётов только на черном фоне"""
        if len(self.enemies) >= target_enemies:
            return

        self.enemy_spawn_timer -= delta_time

        if self.enemy_spawn_timer <= 0 and self.free_spawn_areas:
            # Пытаемся найти подходящую позицию несколько раз
            for attempt in range(100):  # Максимум 100 попыток
                # Используем только свободные области для спавна
                spawn_pos = random.choice(self.free_spawn_areas)
                x, y = spawn_pos

                # Проверяем все условия
                if (self._is_position_free(x, y) and
                        self._is_position_far_from_other_enemies(x, y, min_distance=150)):

                    # Проверка расстояния до игрока (не спавнить слишком близко)
                    if self.player:
                        distance_to_player = math.sqrt((x - self.player.x) ** 2 +
                                                       (y - self.player.y) ** 2)
                        if distance_to_player > 250:  # Минимальное расстояние от игрока
                            enemy = Plane(x, y, COLOR_GREEN_DARK, False)
                            # Направляем врага в случайную сторону
                            enemy.angle = random.choice([0, 90, 180, 270])
                            enemy.target_angle = enemy.angle
                            self.enemies.append(enemy)
                            self.enemy_spawn_timer = ENEMY_SPAWN_DELAY
                            break  # Успешно создали врага
            else:
                # Если не нашли подходящую позицию за 100 попыток
                self.enemy_spawn_timer = ENEMY_SPAWN_DELAY / 2  # Уменьшаем задержку

    def _check_collisions(self):
        """Проверка всех столкновений"""
        if not self.player:
            return

        # Пули игрока с врагами
        for bullet in self.bullets[:]:
            for enemy in self.enemies[:]:
                distance = math.sqrt((bullet.x - enemy.x) ** 2 +
                                     (bullet.y - enemy.y) ** 2)
                if distance < ENEMY_SIZE + BULLET_SIZE:
                    if bullet in self.bullets:
                        self.bullets.remove(bullet)

                    # Эффект уничтожения врага
                    self.particle_system.add_explosion(enemy.x, enemy.y,
                                                       (255, 0, 0), 30)
                    self.camera.shake(8, 0.2)

                    # Начисление очков
                    self.score += 100
                    self.enemies_killed += 1

                    if enemy in self.enemies:
                        self.enemies.remove(enemy)
                    break

        # Пули врагов с игроком
        for bullet in self.enemy_bullets[:]:
            distance = math.sqrt((bullet.x - self.player.x) ** 2 +
                                 (bullet.y - self.player.y) ** 2)
            if distance < PLAYER_SIZE + BULLET_SIZE:
                # Эффект попадания в игрока
                self.particle_system.add_explosion(self.player.x, self.player.y,
                                                   (255, 100, 100), 50)
                self.camera.shake(15, 0.5)

                self.state = GameState.GAME_OVER
                self.animation_timer = ANIMATION_DURATION
                return

        # Враги с игроком
        for enemy in self.enemies:
            distance = math.sqrt((enemy.x - self.player.x) ** 2 +
                                 (enemy.y - self.player.y) ** 2)
            if distance < PLAYER_SIZE + ENEMY_SIZE:
                # Эффект столкновения
                self.particle_system.add_explosion(
                    (self.player.x + enemy.x) / 2,
                    (self.player.y + enemy.y) / 2,
                    (255, 50, 50), 40
                )
                self.camera.shake(20, 0.6)

                self.state = GameState.GAME_OVER
                self.animation_timer = ANIMATION_DURATION
                return

    def on_key_press(self, key: int, modifiers: int):
        """Обработка нажатия клавиш"""
        if self.state == GameState.READY and key == arcade.key.R:
            self.state = GameState.PLAYING
            self.level_start_time = self.game_time
            self.animation_timer = ANIMATION_DURATION

        elif self.state == GameState.PLAYING and self.player:
            if key == arcade.key.W:
                self.player.set_movement(up=True)
            elif key == arcade.key.S:
                self.player.set_movement(down=True)
            elif key == arcade.key.A:
                self.player.set_movement(left=True)
            elif key == arcade.key.D:
                self.player.set_movement(right=True)

        elif self.state == GameState.WIN and self.name_input_active:
            if key == arcade.key.ENTER:
                if self.name_input:
                    self.high_score_manager.add_score(
                        self.name_input,
                        self.score,
                        len(LEVELS)
                    )
                    self.name_input_active = False
                    self.name_input = ""
            elif key == arcade.key.BACKSPACE:
                self.name_input = self.name_input[:-1]
            elif key == arcade.key.SPACE:
                self.name_input += " "
            elif hasattr(key, 'char') and key.char:
                if len(self.name_input) < 15 and key.char.isalnum():
                    self.name_input += key.char

    def on_key_release(self, key: int, modifiers: int):
        """Обработка отпускания клавиш"""
        if self.state == GameState.PLAYING and self.player:
            if key == arcade.key.W:
                self.player.set_movement(up=False)
            elif key == arcade.key.S:
                self.player.set_movement(down=False)
            elif key == arcade.key.A:
                self.player.set_movement(left=False)
            elif key == arcade.key.D:
                self.player.set_movement(right=False)

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        """Обработка нажатия мыши"""
        if self.animation_timer > 0:
            return

        # Проверка кнопок для всех состояний
        if self.state == GameState.MENU:
            if self.button_start.is_clicked(x, y):
                self.state = GameState.RULES
                self.animation_timer = ANIMATION_DURATION
            elif self.button_high_scores.is_clicked(x, y):
                self.state = GameState.HIGH_SCORES
                self.animation_timer = ANIMATION_DURATION

        elif self.state == GameState.RULES:
            if self.button_continue.is_clicked(x, y):
                self.current_level = 0
                self.score = 0
                self.enemies_killed = 0
                self.time_survived = 0
                self.setup()
                self.state = GameState.READY
                self.animation_timer = ANIMATION_DURATION

        elif self.state == GameState.GAME_OVER:
            if self.button_restart.is_clicked(x, y):
                self.setup()
                self.state = GameState.RULES
                self.animation_timer = ANIMATION_DURATION
            elif self.button_menu.is_clicked(x, y):
                self.setup()
                self.state = GameState.MENU
                self.animation_timer = ANIMATION_DURATION

        elif self.state == GameState.WIN and not self.name_input_active:
            if self.button_win_restart.is_clicked(x, y):
                self.current_level = 0
                self.score = 0
                self.enemies_killed = 0
                self.time_survived = 0
                self.setup()
                self.state = GameState.RULES
                self.animation_timer = ANIMATION_DURATION
            elif self.button_win_menu.is_clicked(x, y):
                self.setup()
                self.state = GameState.MENU
                self.animation_timer = ANIMATION_DURATION
            elif self.button_high_scores.is_clicked(x, y):
                self.state = GameState.HIGH_SCORES
                self.animation_timer = ANIMATION_DURATION

        elif self.state == GameState.LEVEL_COMPLETE:
            if self.current_level + 1 < len(LEVELS):
                if self.button_next_level.is_clicked(x, y):
                    self.current_level += 1
                    self.setup()
                    self.state = GameState.READY
                    self.animation_timer = ANIMATION_DURATION
            if self.button_menu.is_clicked(x, y):
                self.setup()
                self.state = GameState.MENU
                self.animation_timer = ANIMATION_DURATION

        elif self.state == GameState.HIGH_SCORES:
            if self.button_back_to_menu.is_clicked(x, y):
                self.state = GameState.MENU
                self.animation_timer = ANIMATION_DURATION

        elif self.state == GameState.PLAYING and button == arcade.MOUSE_BUTTON_LEFT:
            self.is_shooting = True

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int):
        """Обработка отпускания кнопки мыши"""
        if self.state == GameState.PLAYING and button == arcade.MOUSE_BUTTON_LEFT:
            self.is_shooting = False

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        """Обработка движения мыши"""
        # Обновление состояния наведения для всех кнопок
        mouse_states = [
            (GameState.MENU, [self.button_start, self.button_high_scores]),
            (GameState.RULES, [self.button_continue]),
            (GameState.GAME_OVER, [self.button_restart, self.button_menu]),
            (GameState.WIN, [self.button_win_restart, self.button_win_menu, self.button_high_scores]),
            (GameState.LEVEL_COMPLETE, [self.button_next_level, self.button_menu]),
            (GameState.HIGH_SCORES, [self.button_back_to_menu]),
        ]

        for state, buttons in mouse_states:
            if self.state == state:
                for button in buttons:
                    button.is_clicked(x, y)

        if self.state == GameState.PLAYING and self.player:
            # Поворот самолёта в сторону курсора (учитывая смещение камеры)
            world_x = x + self.camera.offset_x
            world_y = y + self.camera.offset_y
            angle = math.degrees(math.atan2(world_y - self.player.y, world_x - self.player.x))
            self.player.angle = angle


# ========== ЗАПУСК ИГРЫ ==========
def main():
    """Главная функция"""
    window = Plane1990()
    window.setup()
    arcade.run()


if __name__ == "__main__":
    main()
