import random
from enum import Enum

'''
Minimal Usage (Example)

if __name__ == "__main__":
    p = PRNGPlayer(seed=42)
    for _ in range(5):
        p.tick()
        print(p)           # pretty print
        # print(p.as_dict())  # To convert to json as application payload.
'''

class MovementState(Enum):
    CROUCHING = 1
    PRONING = 2
    WALKING = 3
    RUNNING = 4


class PRNGPlayer:
    """
    Very simple mock player:
    - Random-walk position
    - Vel is just the last delta
    - State flips occasionally
    """
    def __init__(self, seed: int = 0):
        self.random = random.Random(seed)
        self.pos = [0, 0, 0]
        self.vel = [0, 0, 0]
        self.state = MovementState.WALKING

    def simulate_position(self, step_range: int = 3):
        """
        Randomly nudge position by small integer deltas.
        Updates self.vel to the delta used.
        """
        dx = self.random.randint(-step_range, step_range)
        dy = self.random.randint(-step_range, step_range)
        dz = self.random.randint(-step_range, step_range)

        # update velocity as last movement delta
        self.vel = [dx, dy, dz]

        # apply
        self.pos[0] += dx
        self.pos[1] += dy
        self.pos[2] += dz

    def simulate_state(self, p_change: float = 0.05):
        """
        With small probability, pick a different movement state.
        """
        if self.random.random() < p_change:
            choices = [s for s in MovementState if s != self.state]
            self.state = self.random.choice(choices)

    def tick(self):
        """
        One simple simulation tick.
        """
        self.simulate_position()
        self.simulate_state()

    def as_dict(self):
        """
        For JSON/logging.
        """
        return {
            "pos": list(self.pos),
            "vel": list(self.vel),
            "state": self.state.name,
        }

    def __str__(self):
        return (
            "COORDINATES:\n"
            f"X: {self.pos[0]}\n"
            f"Y: {self.pos[1]}\n"
            f"Z: {self.pos[2]}\n"
            "VELOCITIES:\n"
            f"X: {self.vel[0]}\n"
            f"Y: {self.vel[1]}\n"
            f"Z: {self.vel[2]}\n"
            "STATE:\n"
            f"{self.state.name}\n"
        )



