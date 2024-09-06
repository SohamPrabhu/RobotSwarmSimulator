import math
import random
import numpy as np
from typing import List, Tuple
import pygame
import pygame.draw
from ..agent.Agent import Agent
from ..agent.DiffDriveAgent import DifferentialDriveAgent
from .. agent.HumanAgent import HumanDrivenAgent
from ..config.WorldConfig import RectangularWorldConfig
from ..agent.AgentFactory import AgentFactory
from ..config.HeterogenSwarmConfig import HeterogeneousSwarmConfig
from .World import World
from ..util.timer import Timer
from ..util.collider.AABB import AABB
from .goals.Goal import CylinderGoal
from .objects.Wall import Wall


min_zoom = 0.0001


def distance(pointA, pointB) -> float:
    return math.dist(pointA, pointB)


class RectangularWorld(World):
    def __init__(self, config: RectangularWorldConfig = None):
        if config is None:
            raise Exception("RectangularWorld must be instantiated with a WorldConfig class")

        super().__init__(config.w, config.h, config.metadata)
        self.config = config
        self.population_size = config.population_size
        self.behavior = config.behavior
        self.padding = config.padding
        self.objects = config.objects
        self.goals = config.goals
        self.seed = config.seed
        self.zoom = 1.0
        self._original_zoom = 1.0
        self.pos = np.array([0.0, 0.0])
        self._mouse_dragging_last_pos = np.array([0.0, 0.0])

        self.selected = None
        self.highlighted_set = []
        self.human_controlled = []

        if config.seed is not None:
            # print(f"World Instantiated with Seed: {config.seed}")
            # print(f"TESTING RAND: {random.random()}")
            random.seed(config.seed)

        self.heterogeneous = False

        if isinstance(config.agentConfig, HeterogeneousSwarmConfig):
            self.population = config.agentConfig.build_agent_population()
            self.heterogeneous = True

        else:
            self.population = [
                config.agentConfig.create(name=f"{i}") for i in range(int(self.population_size))
            ]

        # Attach Walls to sensors
        # TODO: Better software engineering here
        if config.detectable_walls:
            from ..sensors.BinaryFOVSensor import BinaryFOVSensor

            self.objects += [
                Wall(self, self.padding - 1, self.padding - 1, 1, self.config.h),
                Wall(self, self.padding - 1, self.padding - 1, self.config.w, 1),
                Wall(self, self.padding - 1, self.padding + self.config.h + 1, self.config.w, 1),
                Wall(self, self.padding + self.config.h + 1, self.padding - 1, 1, self.config.h),
            ]

        ac = config.agentConfig

        # Iniitalize the Agents
        if config.init_type:
            config.init_type.set_to_world(self)

        else:  # TODO: Deprecate defined_start
            if config.defined_start:
                for i in range(len(config.agent_init)):
                    init = config.agent_init[i]
                    noise_x = ((np.random.random() * 2) - 1) * 20
                    noise_y = ((np.random.random() * 2) - 1) * 20
                    noise_theta = ((np.random.random() * 2) - 1) * (np.pi / 8)
                    # noise_x = 0
                    # noise_y = 0
                    # noise_theta = 0
                    self.population[i].set_x_pos(init[0] + noise_x)
                    self.population[i].set_y_pos(init[1] + noise_y)
                    if len(init) > 2:
                        self.population[i].angle = init[2] + noise_theta

            elif self.heterogeneous:
                for agent in self.population:
                    agent.set_x_pos(random.uniform(math.floor(0 + agent.radius), math.floor(self.bounded_width - agent.radius)))
                    agent.set_y_pos(random.uniform(math.ceil(0 + agent.radius), math.floor(self.bounded_height - agent.radius)))
                    agent.angle = random.random() * 2 * math.pi

            elif ac.x is None and config.seed is not None:
                for agent in self.population:
                    agent.set_x_pos(random.uniform(0 + ac.agent_radius, ac.world.w - ac.agent_radius))
                    agent.set_y_pos(random.uniform(0 + ac.agent_radius, ac.world.h - ac.agent_radius))
                    agent.angle = random.random() * 2 * math.pi

        for i in range(len(self.objects)):
            self.objects[i].world = self

        # Assign Agents Identifiers
        for i, agent in enumerate(self.population):
            agent.set_name(str(i))

        self.behavior = config.behavior
        for b in self.behavior:
            b.reset()
            b.attach_world(self)

    def step(self):
        """
        Cycle through the entire population and take one step. Calculate Behavior if needed.
        """
        super().step()
        agent_step_timer = Timer("Population Step")
        for agent in self.population:
            if not issubclass(type(agent), Agent):
                raise Exception("Agents must be subtype of Agent, not {}".format(type(agent)))

            agent.step(
                check_for_world_boundaries=self.withinWorldBoundaries if self.config.collide_walls else None,
                check_for_agent_collisions=self.preventAgentCollisions,
                world=self
            )
            self.handleGoalCollisions(agent)
        # agent_step_timer.check_watch()

        behavior_timer = Timer("Behavior Calculation Step")
        for behavior in self.behavior:
            behavior.calculate()
        # behavior_timer.check_watch()

    def draw(self, screen, offset=None):
        """
        Cycle through the entire population and draw the agents. Draw Environment Walls if needed.
        """
        if offset is None:
            offset = (self.pos, self.zoom)
        pan, zoom = np.asarray(offset[0], dtype=np.int32), offset[1]
        if self.config.show_walls:
            p = self.config.padding * zoom
            size = np.array((self.config.w, self.config.h)) * zoom
            pad = np.array((p, p))
            a = pan + pad  # upper left corner
            b = pan + size - pad * 2
            pygame.draw.rect(screen, (200, 200, 200), pygame.Rect(a, b), 1)

        for world_obj in self.objects:
            world_obj.draw(screen, offset)

        for world_goal in self.goals:
            world_goal.draw(screen, offset)

        for agent in self.population:
            if not issubclass(type(agent), Agent):
                raise Exception("Agents must be subtype of Agent, not {}".format(type(agent)))
            agent.draw(screen, offset)

    def getNeighborsWithinDistance(self, center: Tuple, r, excluded=None) -> List:
        """
        Given the center of a circle, find all Agents located within the circumference defined by center and r
        """
        filtered_agents = []
        for agent in self.population:
            if not issubclass(type(agent), Agent):
                raise Exception("Agents must be subtype of Agent, not {}".format(type(agent)))
            if distance(center, (agent.get_x_pos(), agent.get_y_pos())) < r:
                if agent != excluded:
                    filtered_agents.append(agent)
        return filtered_agents

    def onClick(self, event) -> None:
        viewport_pos = np.asarray(event.pos)
        pos = (viewport_pos - self.pos) / self.zoom
        d = self.population[0].radius * 1.1
        neighborhood = self.getNeighborsWithinDistance(pos, d)

        # Remove Highlights from all agents
        if self.selected is not None:
            self.selected.is_highlighted = False

        if len(neighborhood) == 0:
            self.selected = None
            if self.gui is not None:
                self.gui.set_selected(None)
            return

        self.selected = neighborhood[0]
        if self.gui is not None:
            self.gui.set_selected(neighborhood[0])
            neighborhood[0].is_highlighted = True

    def onZoom(self, mouse_event, scroll_event):
        if not (mouse_event.type == pygame.MOUSEBUTTONUP and scroll_event.type == pygame.MOUSEWHEEL):
            raise TypeError("Expected a mouse button up and scroll event.")

        pos = np.asarray(mouse_event.pos)
        v = scroll_event.precise_y
        self.do_zoom(pos, v)

    def do_zoom(self, point, v):
        v *= 0.4
        old_zoom = self.zoom
        self.zoom = self.zoom * (2 ** v)
        self.zoom = max(self.zoom, min_zoom)
        # print(f"zoom: {round(old_zoom, 6): >10f} --> {round(self.zoom, 6): >10f}")
        point = point.astype(np.float64)
        center_px = np.array([self.config.w, self.config.h]) / 2
        point -= center_px
        self.pos = (self.pos - point) * self.zoom / old_zoom + point

    def zoom_reset(self):
        self.zoom = self.original_zoom
        self.pos = np.array([0.0, 0.0])

    @property
    def original_zoom(self):
        return self._original_zoom

    @original_zoom.setter
    def original_zoom(self, value):
        self._original_zoom = value
        self.zoom = value

    def handle_middle_mouse_events(self, events):
        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN:
                self._mouse_dragging_last_pos = np.asarray(event.pos)

    def handle_middle_mouse_held(self, pos):
        pos = np.asarray(pos)
        delta = pos - self._mouse_dragging_last_pos
        self.pos += delta
        self._mouse_dragging_last_pos = pos

    def withinWorldBoundaries(self, agent: DifferentialDriveAgent):
        """
        Set agent position with respect to the world's boundaries and the bounding box of the agent
        """
        padding = self.padding

        old_x, old_y = agent.get_x_pos(), agent.get_y_pos()

        # Prevent Left Collisions
        agent.set_x_pos(max(agent.radius + padding, agent.get_x_pos()))

        # Prevent Right Collisions
        agent.set_x_pos(min((self.bounded_width - agent.radius - padding), agent.get_x_pos()))

        # Prevent Top Collisions
        agent.set_y_pos(max(agent.radius + padding, agent.get_y_pos()))

        # Prevent Bottom Collisions
        agent.set_y_pos(min((self.bounded_height - agent.radius - padding), agent.get_y_pos()))

        # agent.angle += (math.pi / 720)
        self.handleWallCollisions(agent)

        if agent.get_x_pos() != old_x or agent.get_y_pos() != old_y:
            return True
        return False

    def handleGoalCollisions(self, agent):
        for goal in self.goals:
            if isinstance(goal, CylinderGoal):
                correction = agent.build_collider().collision_then_correction(goal.get_collider())
                if correction is not None:
                    agent.set_x_pos(agent.get_x_pos() + correction[0])
                    agent.set_y_pos(agent.get_y_pos() + correction[1])

    def handleWallCollisions(self, agent: DifferentialDriveAgent):
        # Check for distances between the agent and the line segments
        in_collision = False
        for obj in self.objects:
            segs = obj.get_sensing_segments()
            c = (agent.get_x_pos(), agent.get_y_pos())
            for p1, p2 in segs:
                # From https://stackoverflow.com/questions/24727773/detecting-rectangle-collision-with-a-circle
                x1, y1 = p1
                x2, y2 = p2
                x3, y3 = c
                px = x2 - x1
                py = y2 - y1

                something = px * px + py * py

                u = ((x3 - x1) * px + (y3 - y1) * py) / float(something)

                if u > 1:
                    u = 1
                elif u < 0:
                    u = 0

                x = x1 + u * px
                y = y1 + u * py

                dx = x - x3
                dy = y - y3

                dist = math.sqrt(dx * dx + dy * dy)

                if dist < agent.radius:
                    in_collision = True
                    agent.set_y_pos(agent.get_y_pos() - (np.sign(dy) * (agent.radius - abs(dy) + 1)))
                    agent.set_x_pos(agent.get_x_pos() - (np.sign(dx) * (agent.radius - abs(dx) + 1)))

                # dx = x - x3 - agent.radius
                # if dx < 0:
                #     in_collision = True
                #     agent.set_x_pos(agent.get_x_pos() - dx)
                # dy = y - y3 - agent.radius
                # if dy < 0:
                #     in_collision = True
                #     agent.set_y_pos(agent.get_y_pos() - dy)

        return in_collision

    def preventAgentCollisions(self, agent: DifferentialDriveAgent, forward_freeze=False) -> None:
        agent_center = agent.getPosition()
        minimum_distance = agent.radius * 2
        target_distance = minimum_distance + 0.001

        neighborhood = self.getNeighborsWithinDistance(agent_center, minimum_distance, excluded=agent)
        if len(neighborhood) == 0:
            return

        remaining_attempts = 10
        while len(neighborhood) > 0 and remaining_attempts > 0:

            # Check ALL Bagged agents for collisions
            for i in range(len(neighborhood)):
                colliding_agent = neighborhood[i]

                if not agent.get_aabb().intersects(colliding_agent.get_aabb()):
                    continue

                center_distance = distance(agent_center, colliding_agent.getPosition())
                if center_distance > minimum_distance:
                    # colliding_agent.collision_flag = False
                    continue

                if agent.stop_on_collision:
                    agent.stopped_duration = 3

                agent.collision_flag = True
                colliding_agent.collision_flag = True
                if colliding_agent.detection_id == 2:
                    agent.detection_id = 2

                # print(f"Overlap. A: {agent_center}, B: {colliding_agent.getPosition()}")
                distance_needed = target_distance - center_distance
                a_to_b = colliding_agent.getPosition() - agent_center
                b_to_a = agent_center - colliding_agent.getPosition()

                # Check to see if the collision takes place in the forward facing direction
                if forward_freeze and self.collision_forward(agent, colliding_agent):
                    continue

                # If distance super close to 0, we have a problem. Add noise.
                SIGNIFICANCE = 0.0001
                if b_to_a[0] < SIGNIFICANCE and b_to_a[1] < SIGNIFICANCE:
                    MAGNITUDE = 0.001
                    direction = 1
                    if random.random() > 0.5:
                        direction = -1
                    agent.set_x_pos(agent.get_x_pos() + (random.random() * direction * MAGNITUDE))

                    direction = 1
                    if random.random() > 0.5:
                        direction = -1
                    agent.set_y_pos(agent.get_y_pos() + (random.random() * direction * MAGNITUDE))

                    agent_center = agent.getPosition()
                    center_distance = distance(agent_center, colliding_agent.getPosition())
                    distance_needed = target_distance - center_distance
                    b_to_a = agent_center - colliding_agent.getPosition()

                pushback = (b_to_a / np.linalg.norm(b_to_a)) * distance_needed

                # print(base, a_to_b, theta)
                delta_x = pushback[0]
                delta_y = pushback[1]

                if math.isnan(delta_x) or math.isnan(delta_y):
                    break

                agent.set_x_pos(agent.get_x_pos() + delta_x)
                agent.set_y_pos(agent.get_y_pos() + delta_y)
                agent_center = agent.getPosition()

            neighborhood = self.getNeighborsWithinDistance(agent_center, minimum_distance, excluded=agent)
            remaining_attempts -= 1

    def getAgentsMatchingYRange(self, bb: AABB):
        ret = []
        for agent in self.population:
            if bb.in_y_range(agent.get_aabb()):
                ret.append(agent)
        return ret

    def getBehaviorVector(self):
        behavior = np.array([s.out_average()[1] for s in self.behavior])
        return behavior

    def removeAgent(self, agent):
        agent.deleted = True
        self.population.remove(agent)

    def collision_forward(self, agent, colliding_agent):
        a_to_b = colliding_agent.getPosition() - agent.getPosition()
        b_to_a = agent.getPosition() - colliding_agent.getPosition()
        heading = agent.getFrontalPoint()
        dot = np.dot(a_to_b, heading)
        mag_a = np.linalg.norm(a_to_b)
        mag_b = np.linalg.norm(heading)
        angle = np.arccos(dot / (mag_a * mag_b))
        degs = np.degrees(abs(angle))
        if degs < 30:
            # print(f"Collision at angle {degs}.")
            agent.stopped_duration = 2
            return True

        # Now Calculate B_to_A
        heading = colliding_agent.getFrontalPoint()
        dot = np.dot(b_to_a, heading)
        mag_a = np.linalg.norm(b_to_a)
        mag_b = np.linalg.norm(heading)
        angle = np.arccos(dot / (mag_a * mag_b))
        degs = np.degrees(abs(angle))
        if degs < 30:
            # print(f"Collision at angle {degs}.")
            colliding_agent.stopped_duration = 2
            return True
        return False

    def handle_key_press(self, event):
        for a in self.population:
            a.on_key_press(event)

        if self.selected is not None:
            if event.key == pygame.K_l:
                self.selected.simulate_error("Death")
            if event.key == pygame.K_o:
                self.selected.simulate_error("Divergence")
            if event.key == pygame.K_p:
                self.removeAgent(self.selected)
            if event.key == pygame.K_a:
                COLORS = [(247, 146, 86), (146, 220, 229), (235, 185, 223), (251, 209, 162), (99, 105, 209)]
                self.selected.body_color = COLORS[len(self.highlighted_set) % len(COLORS)]
                self.selected.is_highlighted = True
                self.highlighted_set.append(self.selected)
            if event.key == pygame.K_h:
                i = self.population.index(self.selected)
                new_human = HumanDrivenAgent(self.selected.config)
                new_human.x_pos = self.selected.x_pos
                new_human.y_pos = self.selected.y_pos
                new_human.angle = self.selected.angle
                self.population[i] = new_human
                self.human_controlled.append(new_human)

        if event.key == pygame.K_c:
            for agent in self.highlighted_set:
                agent.is_highlighted = False
                agent.body_color = agent.config.body_color
            for agent in self.human_controlled:
                i = self.population.index(agent)
                new_bot = DifferentialDriveAgent(agent.config)
                new_bot.x_pos = agent.get_x_pos()
                new_bot.y_pos = agent.get_y_pos()
                new_bot.angle = agent.angle
                self.population[i] = new_bot
            self.human_controlled = []
            self.highlighted_set = []

    def handle_held_keys(self, keys):
        for agent in self.human_controlled:
            agent.handle_key_press(keys)

    def as_config_dict(self):
        return self.config.as_dict()

