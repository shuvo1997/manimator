"""
Dynamic example injection — detects animation category from user prompt and
returns a short verified working Manim snippet to append to the system prompt.
"""
from __future__ import annotations

# ── Category keyword mapping ──────────────────────────────────────────────────

CATEGORIES: dict[str, list[str]] = {
    "tree": [
        "tree", "bst", "binary search tree", "heap", "trie", "avl",
        "binary tree", "traversal", "inorder", "preorder", "postorder",
        "insert node", "tree node",
    ],
    "graph": [
        "graph", "dfs", "bfs", "dijkstra", "adjacency", "shortest path",
        "depth first", "breadth first", "topological", "connected components",
        "minimum spanning tree", "bellman", "kruskal", "prim",
    ],
    "sort": [
        "sort", "bubble sort", "merge sort", "quicksort", "quick sort",
        "insertion sort", "selection sort", "counting sort", "heap sort",
        "radix sort", "sorting algorithm",
    ],
    "search": [
        "binary search", "linear search", "search algorithm",
    ],
    "dp": [
        "dynamic programming", " dp ", "memoization", "knapsack",
        "fibonacci", "longest common subsequence", "edit distance",
        "coin change", "tabulation", "bottom-up", "top-down",
    ],
    "array": [
        "array", "two sum", "sliding window", "two pointer", "subarray",
        "max subarray", "kadane", "prefix sum",
    ],
    "linked_list": [
        "linked list", "singly linked", "doubly linked", "reverse linked",
    ],
    "stack_queue": [
        "stack", "queue", "deque", "push", "pop", "enqueue", "dequeue",
    ],
}

# ── Verified working Manim snippets (one per category) ───────────────────────

_TREE_EXAMPLE = '''\
## VERIFIED TREE / BST PATTERN — copy this structure exactly

```python
from manimlib import *

class GeneratedScene(Scene):
    def construct(self):
        # Helper: create a labeled circle node
        def make_node(val, color=BLUE_E):
            circle = Circle(radius=0.42, color=WHITE, fill_color=color, fill_opacity=0.85)
            label = Text(str(val), font_size=28, color=WHITE).move_to(circle)
            return VGroup(circle, label)

        # Helper: draw edge between two nodes (connects circle surfaces, not centers)
        def make_edge(n1, n2, color=GREY_B):
            start = n1.get_center()
            end   = n2.get_center()
            direction = end - start
            length = np.linalg.norm(direction)
            unit = direction / length
            # pull endpoints back by circle radius (0.42) + small gap
            return Line(
                start + unit * 0.46,
                end   - unit * 0.46,
                color=color, stroke_width=2,
            )

        import numpy as np

        # ── Layout: place nodes at fixed positions in safe zone ──────────
        # Safe zone: x ∈ [-6, 6], y ∈ [-3.5, 3.5]
        # Root at top, children below with horizontal spread

        root  = make_node(8).move_to(UP * 2.5)
        left  = make_node(3).move_to(LEFT * 2.5 + UP * 0.8)
        right = make_node(10).move_to(RIGHT * 2.5 + UP * 0.8)
        ll    = make_node(1).move_to(LEFT * 4   + DOWN * 0.9)
        lr    = make_node(6).move_to(LEFT * 1.2 + DOWN * 0.9)
        rr    = make_node(14).move_to(RIGHT * 4  + DOWN * 0.9)

        nodes = VGroup(root, left, right, ll, lr, rr)

        # ── Draw edges BEFORE nodes (so they appear behind circles) ──────
        edges = VGroup(
            make_edge(root, left),
            make_edge(root, right),
            make_edge(left, ll),
            make_edge(left, lr),
            make_edge(right, rr),
        )

        title = Text("Binary Search Tree", font_size=36).to_edge(UP, buff=0.3)
        self.play(Write(title))
        self.play(ShowCreation(edges), run_time=1.2)
        self.play(FadeIn(nodes), run_time=0.8)
        self.wait(1)

        # ── Animate a search / insertion step ────────────────────────────
        step = Text("Search: 6", font_size=26, color=YELLOW).to_edge(DOWN, buff=0.5)
        self.play(Write(step))
        self.wait(0.5)

        # Highlight root
        self.play(root[0].animate.set_fill(YELLOW, opacity=0.9), run_time=0.4)
        self.wait(0.4)
        next_step = Text("6 < 8 → go left", font_size=26, color=YELLOW).to_edge(DOWN, buff=0.5)
        self.play(Transform(step, next_step))   # ← Transform replaces label in-place, no overlap

        self.play(root[0].animate.set_fill(BLUE_E, opacity=0.85), run_time=0.3)
        self.play(left[0].animate.set_fill(YELLOW, opacity=0.9), run_time=0.4)
        self.wait(0.4)
        next_step2 = Text("6 > 3 → go right", font_size=26, color=YELLOW).to_edge(DOWN, buff=0.5)
        self.play(Transform(step, next_step2))

        self.play(left[0].animate.set_fill(BLUE_E, opacity=0.85), run_time=0.3)
        self.play(lr[0].animate.set_fill(GREEN, opacity=0.95), run_time=0.4)
        found_step = Text("Found: 6  ✓", font_size=26, color=GREEN).to_edge(DOWN, buff=0.5)
        self.play(Transform(step, found_step))
        self.wait(2)
```

KEY RULES for trees/graphs:
- make_node() returns VGroup(circle, label) — position the VGroup, NOT the circle separately
- make_edge() connects circle surfaces: start + unit*0.46, end - unit*0.46 (radius 0.42 + 0.04 gap)
- Draw edges BEFORE nodes (so edges appear behind circles)
- All node positions must stay in safe zone: x ∈ [-5, 5], y ∈ [-2.5, 2.8]
- Use Transform(step_label, new_label) to update step text — NEVER write a new label without removing the old one
'''

_GRAPH_EXAMPLE = '''\
## VERIFIED GRAPH PATTERN — copy this structure exactly

```python
from manimlib import *
import numpy as np

class GeneratedScene(Scene):
    def construct(self):
        def make_node(label, pos, color=BLUE_D):
            c = Circle(radius=0.38, color=WHITE, fill_color=color, fill_opacity=0.9)
            c.move_to(pos)
            t = Text(str(label), font_size=26, color=WHITE).move_to(c)
            return VGroup(c, t)

        def make_edge(n1, n2, directed=False, color=GREY_B, weight=None):
            s, e = n1.get_center(), n2.get_center()
            d = e - s
            u = d / np.linalg.norm(d)
            gap = 0.42
            if directed:
                edge = Arrow(s + u*gap, e - u*gap, buff=0, color=color, stroke_width=2.5)
            else:
                edge = Line(s + u*gap, e - u*gap, color=color, stroke_width=2)
            result = VGroup(edge)
            if weight is not None:
                mid = (s + e) / 2
                perp = np.array([-u[1], u[0], 0]) * 0.28
                wt = Text(str(weight), font_size=20, color=YELLOW).move_to(mid + perp)
                result.add(wt)
            return result

        # ── Node positions (safe zone: x ∈ [-5,5], y ∈ [-2.5, 2.8]) ────
        positions = {
            "A": np.array([-3.5,  1.5, 0]),
            "B": np.array([ 0.0,  2.2, 0]),
            "C": np.array([ 3.5,  1.5, 0]),
            "D": np.array([-2.0, -0.5, 0]),
            "E": np.array([ 2.0, -0.5, 0]),
        }
        nodes = {k: make_node(k, v) for k, v in positions.items()}

        edges_data = [("A","B",4), ("A","D",2), ("B","C",3),
                      ("B","E",5), ("D","E",1), ("C","E",6)]
        edge_objs = VGroup(*[
            make_edge(nodes[a], nodes[b], directed=True, weight=w)
            for a, b, w in edges_data
        ])

        title = Text("Dijkstra Shortest Path", font_size=34).to_edge(UP, buff=0.3)
        self.play(Write(title))
        self.play(ShowCreation(edge_objs), run_time=1.5)
        self.play(FadeIn(VGroup(*nodes.values())), run_time=0.8)
        self.wait(1)

        step = Text("Start at A, distance = 0", font_size=24, color=YELLOW).to_edge(DOWN, buff=0.5)
        self.play(Write(step))
        self.play(nodes["A"][0].animate.set_fill(YELLOW, opacity=0.95), run_time=0.4)
        self.wait(0.6)

        next_step = Text("Explore A→D (cost 2), A→B (cost 4)", font_size=24, color=YELLOW).to_edge(DOWN, buff=0.5)
        self.play(Transform(step, next_step))
        self.wait(2)
```
'''

_SORT_EXAMPLE = '''\
## VERIFIED SORT PATTERN — copy this structure exactly

```python
from manimlib import *

class GeneratedScene(Scene):
    def construct(self):
        values = [5, 3, 8, 1, 4, 2]
        N = len(values)

        def make_bars(vals):
            bars = VGroup()
            for v in vals:
                bar = Rectangle(width=0.7, height=v * 0.45, color=BLUE_D)
                bar.set_fill(BLUE_D, opacity=0.85)
                lbl = Text(str(v), font_size=24).move_to(bar.get_top() + UP * 0.2)
                bars.add(VGroup(bar, lbl))
            bars.arrange(RIGHT, buff=0.15, aligned_edge=DOWN)
            bars.move_to(ORIGIN + DOWN * 0.5)
            return bars

        title = Text("Bubble Sort", font_size=40, color=BLUE).to_edge(UP, buff=0.3)
        self.play(Write(title))

        arr = list(values)
        bars = make_bars(arr)
        self.play(FadeIn(bars))
        self.wait(0.5)

        step = Text("Pass 1 — compare adjacent pairs", font_size=24, color=WHITE).to_edge(DOWN, buff=0.5)
        self.play(Write(step))

        # One pass of bubble sort
        for i in range(N - 1):
            self.play(
                bars[i][0].animate.set_fill(YELLOW, opacity=0.9),
                bars[i+1][0].animate.set_fill(YELLOW, opacity=0.9),
                run_time=0.25,
            )
            if arr[i] > arr[i+1]:
                arr[i], arr[i+1] = arr[i+1], arr[i]
                swap_text = Text(f"Swap {arr[i+1]} > {arr[i]} → swap", font_size=22, color=ORANGE).to_edge(DOWN, buff=0.5)
                self.play(Transform(step, swap_text), run_time=0.2)
                # Swap bar positions
                self.play(
                    bars[i].animate.move_to(bars[i+1].get_center()),
                    bars[i+1].animate.move_to(bars[i].get_center()),
                    run_time=0.4,
                )
                bars[i], bars[i+1] = bars[i+1], bars[i]
            self.play(
                bars[i][0].animate.set_fill(BLUE_D, opacity=0.85),
                bars[i+1][0].animate.set_fill(BLUE_D, opacity=0.85),
                run_time=0.2,
            )

        # Mark last as sorted
        self.play(bars[-1][0].animate.set_fill(GREEN, opacity=0.9), run_time=0.3)
        done_step = Text("Largest element bubbled to end ✓", font_size=24, color=GREEN).to_edge(DOWN, buff=0.5)
        self.play(Transform(step, done_step))
        self.wait(2)
```
'''

_SEARCH_EXAMPLE = '''\
## VERIFIED BINARY SEARCH PATTERN

```python
from manimlib import *

class GeneratedScene(Scene):
    def construct(self):
        nums = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]
        target = 23

        title = Text("Binary Search", font_size=40, color=BLUE).to_edge(UP, buff=0.3)
        self.play(Write(title))

        cells = VGroup(*[
            Square(side_length=0.75).set_fill(BLUE_E, opacity=0.6)
            for _ in nums
        ]).arrange(RIGHT, buff=0.05).move_to(ORIGIN)
        val_labels = VGroup(*[Text(str(n), font_size=20).move_to(c) for n, c in zip(nums, cells)])
        idx_labels = VGroup(*[Text(str(i), font_size=14, color=GREY_B).next_to(c, DOWN, buff=0.1) for i, c in enumerate(cells)])
        self.play(FadeIn(cells), FadeIn(val_labels), FadeIn(idx_labels))

        step = Text(f"Searching for {target}", font_size=26, color=YELLOW).to_edge(DOWN, buff=0.5)
        self.play(Write(step))
        self.wait(0.5)

        lo, hi = 0, len(nums) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            mid_text = Text(f"lo={lo}, hi={hi}, mid={mid}, nums[mid]={nums[mid]}", font_size=22, color=WHITE).to_edge(DOWN, buff=0.5)
            self.play(Transform(step, mid_text))
            self.play(cells[mid].animate.set_fill(YELLOW, opacity=0.9), run_time=0.4)
            self.wait(0.5)
            if nums[mid] == target:
                found = Text(f"Found {target} at index {mid}!", font_size=26, color=GREEN).to_edge(DOWN, buff=0.5)
                self.play(Transform(step, found))
                self.play(cells[mid].animate.set_fill(GREEN, opacity=0.95), run_time=0.4)
                break
            elif nums[mid] < target:
                self.play(cells[mid].animate.set_fill(GREY, opacity=0.4), run_time=0.3)
                for k in range(lo, mid):
                    self.play(cells[k].animate.set_fill(GREY, opacity=0.3), run_time=0.05)
                lo = mid + 1
            else:
                self.play(cells[mid].animate.set_fill(GREY, opacity=0.4), run_time=0.3)
                hi = mid - 1

        complexity = Text("Time: O(log n)  |  Space: O(1)", font_size=24, color=GREY_B).to_edge(DOWN, buff=0.1)
        self.play(Write(complexity))
        self.wait(2)
```
'''

_DP_EXAMPLE = '''\
## VERIFIED DYNAMIC PROGRAMMING PATTERN (DP Table)

```python
from manimlib import *
import numpy as np

class GeneratedScene(Scene):
    def construct(self):
        # Fibonacci with memoization table — adapt for other DP problems
        n = 8
        dp = [0] * (n + 1)
        dp[1] = 1

        title = Text("Fibonacci DP Table", font_size=36, color=BLUE).to_edge(UP, buff=0.3)
        self.play(Write(title))

        # Draw table cells (safe zone: spread them horizontally)
        cell_size = 0.8
        cells = VGroup(*[
            Square(side_length=cell_size).set_fill(BLUE_E, opacity=0.5)
            for _ in range(n + 1)
        ]).arrange(RIGHT, buff=0.05).move_to(ORIGIN + UP * 0.3)

        idx_labels = VGroup(*[
            Text(f"dp[{i}]", font_size=16, color=GREY_B).next_to(cells[i], UP, buff=0.1)
            for i in range(n + 1)
        ])
        val_labels = [
            Text("?", font_size=22, color=WHITE).move_to(cells[i])
            for i in range(n + 1)
        ]
        val_group = VGroup(*val_labels)

        self.play(FadeIn(cells), FadeIn(idx_labels), FadeIn(val_group))
        self.wait(0.5)

        step = Text("Fill base cases: dp[0]=0, dp[1]=1", font_size=24, color=YELLOW).to_edge(DOWN, buff=0.5)
        self.play(Write(step))

        # Base cases
        for i in [0, 1]:
            new_lbl = Text(str(dp[i]), font_size=22, color=GREEN).move_to(cells[i])
            self.play(
                cells[i].animate.set_fill(GREEN_E, opacity=0.7),
                Transform(val_labels[i], new_lbl),
                run_time=0.4,
            )
        self.wait(0.4)

        # Fill remaining
        for i in range(2, n + 1):
            dp[i] = dp[i-1] + dp[i-2]
            fill_step = Text(f"dp[{i}] = dp[{i-1}] + dp[{i-2}] = {dp[i-1]} + {dp[i-2]} = {dp[i]}", font_size=22, color=YELLOW).to_edge(DOWN, buff=0.5)
            self.play(Transform(step, fill_step))
            self.play(
                cells[i-1].animate.set_fill(YELLOW, opacity=0.7),
                cells[i-2].animate.set_fill(YELLOW, opacity=0.7),
                run_time=0.3,
            )
            new_lbl = Text(str(dp[i]), font_size=22, color=WHITE).move_to(cells[i])
            self.play(
                cells[i].animate.set_fill(BLUE_C, opacity=0.7),
                Transform(val_labels[i], new_lbl),
                run_time=0.4,
            )
            self.play(
                cells[i-1].animate.set_fill(BLUE_E, opacity=0.5),
                cells[i-2].animate.set_fill(BLUE_E, opacity=0.5),
                run_time=0.2,
            )

        result_step = Text(f"fib({n}) = {dp[n]}  |  Time: O(n), Space: O(n)", font_size=24, color=GREEN).to_edge(DOWN, buff=0.5)
        self.play(Transform(step, result_step))
        self.wait(2)
```
'''

_ARRAY_EXAMPLE = '''\
## VERIFIED ARRAY / POINTER PATTERN — use for two-sum, sliding window, two-pointer problems

Key pattern: use Transform(step_label, new_label) for ALL step text updates.
Keep all array cells within safe zone (total width ≤ 11 units).
'''

_STACK_QUEUE_EXAMPLE = '''\
## VERIFIED STACK / QUEUE PATTERN

```python
from manimlib import *

class GeneratedScene(Scene):
    def construct(self):
        title = Text("Stack — Push & Pop", font_size=36, color=BLUE).to_edge(UP, buff=0.3)
        self.play(Write(title))

        # Stack visualized as a column of rectangles growing upward
        stack_base = Rectangle(width=1.8, height=0.1, color=WHITE).move_to(DOWN * 2)
        stack_left  = Line(stack_base.get_corner(UL), stack_base.get_corner(UL) + UP * 3.5, color=WHITE)
        stack_right = Line(stack_base.get_corner(UR), stack_base.get_corner(UR) + UP * 3.5, color=WHITE)
        self.play(ShowCreation(VGroup(stack_base, stack_left, stack_right)))

        items = []
        colors = [BLUE_D, TEAL, GREEN_D, GOLD, MAROON]
        push_values = [3, 7, 1, 9, 4]

        step = Text("Push 3", font_size=26, color=YELLOW).to_edge(DOWN, buff=0.5)
        self.play(Write(step))

        for idx, val in enumerate(push_values):
            cell = Rectangle(width=1.6, height=0.55, color=WHITE)
            cell.set_fill(colors[idx % len(colors)], opacity=0.8)
            lbl = Text(str(val), font_size=26, color=WHITE).move_to(cell)
            item = VGroup(cell, lbl)

            # Position: above the current top of stack
            y_pos = -1.8 + idx * 0.6
            item.move_to(np.array([0, y_pos, 0]))

            new_step = Text(f"Push {val}", font_size=26, color=YELLOW).to_edge(DOWN, buff=0.5)
            self.play(Transform(step, new_step), run_time=0.2)
            self.play(FadeIn(item, shift=DOWN * 0.3), run_time=0.4)
            items.append(item)
            self.wait(0.2)

        # Pop once
        pop_step = Text("Pop → removes top element", font_size=26, color=ORANGE).to_edge(DOWN, buff=0.5)
        self.play(Transform(step, pop_step))
        self.play(FadeOut(items[-1], shift=UP * 0.5), run_time=0.5)
        self.wait(2)
```
'''

EXAMPLES: dict[str, str] = {
    "tree":        _TREE_EXAMPLE,
    "graph":       _GRAPH_EXAMPLE,
    "sort":        _SORT_EXAMPLE,
    "search":      _SEARCH_EXAMPLE,
    "dp":          _DP_EXAMPLE,
    "array":       _ARRAY_EXAMPLE,
    "linked_list": "",   # covered by general array pattern
    "stack_queue": _STACK_QUEUE_EXAMPLE,
}


# ── Public API ────────────────────────────────────────────────────────────────

def detect_category(prompt: str) -> str | None:
    """Return the best-matching category key, or None."""
    p = prompt.lower()
    # Give longer/more specific keywords priority
    best: str | None = None
    best_len = 0
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in p and len(kw) > best_len:
                best = cat
                best_len = len(kw)
    return best


def get_example(prompt: str) -> str | None:
    """
    Return the verified pattern snippet for the detected category, or None.
    Only injects if the snippet is non-empty.
    """
    cat = detect_category(prompt)
    if cat is None:
        return None
    snippet = EXAMPLES.get(cat, "")
    return snippet if snippet.strip() else None
