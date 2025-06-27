import unittest

from novel_swarms.sensors.BinaryFOVSensor import BinaryFOVSensor
from novel_swarms.sensors.AbstractSensor import AbstractSensor
from novel_swarms.agent.MazeAgent import MazeAgent,MazeAgentConfig
from novel_swarms.world.RectangularWorld import RectangularWorldConfig, RectangularWorld
class TestFOVSensor(unittest.TestCase):
    pass


class TestSensorConf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cd: dict = {
            "theta": 0.45,
            "agent_sensing_range": 23,
            "bias": 12,
            "fn": 0.12,
            "fp": 0.1,
            "store_history": False,
            "use_goal_state": True,
            "wall_sensing_range": 23,
            "goal_sensing_range": 19,
        }

        cls.bfv =  BinaryFOVSensor(
            parent=None,
            theta=cls.cd["theta"],
            distance=cls.cd["agent_sensing_range"],
            bias=cls.cd["bias"],
            false_positive=cls.cd.get("fp", 0.0),
            false_negative=cls.cd.get("fn", 0.0),
            store_history=cls.cd["store_history"],
            detect_goal_with_added_state=cls.cd["use_goal_state"],
            wall_sensing_range=cls.cd["wall_sensing_range"],
            goal_sensing_range=cls.cd["goal_sensing_range"],
            seed=cls.cd["seed"] if "seed" in cls.cd else None,
        )

    def test_theta(self):
        self.assertEqual(self.bfv.theta, self.cd["theta"])

    def test_distance(self):
        self.assertEqual(self.bfv.r, self.cd["agent_sensing_range"])

    def test_bias(self):
        self.assertEqual(self.bfv.bias, self.cd["bias"])

    def test_false_values(self):
        self.assertEqual(self.bfv.fn, self.cd["fn"])
        self.assertEqual(self.bfv.fp, self.cd["fp"])

    def test_goal_config(self):
        self.assertEqual(self.bfv.use_goal_state, self.cd["use_goal_state"])
        self.assertEqual(self.bfv.goal_sensing_range, self.cd["goal_sensing_range"])

    def test_wall_config(self):
        self.assertEqual(self.bfv.wall_sensing_range, self.cd["wall_sensing_range"])

    def test_seed(self):
        if "seed" in self.cd:
            self.assertEqual(self.bfv.seed, self.cd["seed"])
        else:
            self.assertIsNone(self.bfv.seed)

class TestAbsSensor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        agetnConf =  MazeAgentConfig()
        world_config = RectangularWorldConfig(size=[10, 10], time_step=1 / 40)
        world = RectangularWorld(world_config)
        parent = MazeAgent(config=agetnConf, world=world)
        agent = MazeAgent(world=world,config=agetnConf)

        cls.cd: dict = {
            "agent": agent,
            "parent": parent,
            "static_position":(0,0),
            "n_possible_states": 2,
            "draw": True
        }
        cls.afb = AbstractSensor(
            agent=cls.cd["agent"],
            parent=cls.cd["parent"],
            n_possible_states=cls.cd["n_possible_states"],
            draw=cls.cd["draw"],
            static_position=cls.cd["static_position"]
        )
    def test_agent(self):
        self.assertEqual(self.cd["agent"],self.afb.agent)
    def test_set_agent(self):
        agetnConf =  MazeAgentConfig()
        world_config = RectangularWorldConfig(size=[10, 10], time_step=1 / 40)
        world = RectangularWorld(world_config)
        new_agent = MazeAgent(config=agetnConf, world=world)
        self.afb.set_agent(new_agent)
        self.assertEqual(new_agent,self.afb.agent)
    def test_parent(self):
        self.assertEqual(self.cd["parent"],self.afb.parent)    
    def test_set_parent(self):
        agetnConf =  MazeAgentConfig()
        world_config = RectangularWorldConfig(size=[10, 10], time_step=1 / 40)
        world = RectangularWorld(world_config)
        new_parent = MazeAgent(config=agetnConf, world=world)
        self.afb.set_parent(new_parent)
        self.assertEqual(new_parent,self.afb.parent)
        
        
    
    