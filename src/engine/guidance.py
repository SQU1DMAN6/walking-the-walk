from dataclasses import dataclass
import heapq
import math


@dataclass(frozen=True)
class ObjectiveDirection:
    target_id: int
    name: str
    relative: float
    distance: float
    remaining: int
    waypoint: tuple
    danger: bool = False


@dataclass(frozen=True)
class ActionCoach:
    kind: str
    text: str
    slot: int | None = None


class PathGuide:
    def __init__(self, paths):
        self.nodes = list(dict.fromkeys(paths.route+[point for branch in paths.branches for point in branch]))
        index = {point: i for i, point in enumerate(self.nodes)}
        self.edges = [[] for _ in self.nodes]
        for a, b in paths.segments:
            i, j = index[a], index[b]
            distance = math.dist(a, b)
            self.edges[i].append((j, distance))
            self.edges[j].append((i, distance))

    def route(self, source, goal):
        start = min(range(len(self.nodes)), key=lambda i: math.dist(source, self.nodes[i]))
        end = min(range(len(self.nodes)), key=lambda i: math.dist(goal, self.nodes[i]))
        queue, costs, previous = [(0, start)], {start: 0}, {}
        while queue:
            cost, node = heapq.heappop(queue)
            if cost != costs[node]:
                continue
            if node == end:
                break
            for other, distance in self.edges[node]:
                candidate = cost+distance
                if candidate < costs.get(other, math.inf):
                    costs[other], previous[other] = candidate, node
                    heapq.heappush(queue, (candidate, other))
        if end not in costs:
            return [], math.inf
        route = [end]
        while route[-1] != start:
            route.append(previous[route[-1]])
        route.reverse()
        return [self.nodes[i] for i in route], math.dist(source, self.nodes[start])+costs[end]+math.dist(self.nodes[end], goal)

    def next_waypoint(self, source, goal):
        route, _ = self.route(source, goal)
        if not route:
            return goal
        if math.dist(source, route[0]) > .9:
            return route[0]
        # Wrong branch? Forest shortcuts aren't the tutorial meta.
        return next((point for point in route[1:] if math.dist(source, point) >= 1.5), goal)
