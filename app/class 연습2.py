from __future__ import annotations

class Brick:
    def __init__(self, size, color):
        self.size = size
        self.color = color

    def __str__(self):
        return str(self.size) + " " + self.color

    def build(self):
        print("laying bricks")


class Hammer:
    @staticmethod
    def hammer():
        print("knocking on a brick")

if __name__ == '__main__':
    brick1 = Brick(100, "red")
    brick2 = Brick(200, "blue")
    print(brick1, brick2)

    Hammer.hammer()