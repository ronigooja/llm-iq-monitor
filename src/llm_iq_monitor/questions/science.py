"""Closed-form science calculations."""

import math
from .base import Question, answer_prompt, rng_for


def generate(seed: str) -> list[Question]:
    out = []
    for i in range(12):
        r = rng_for(seed, "science", i); t = i
        if t == 0: p, v, n, temp = r.randint(90, 120), r.randint(2, 8), r.randint(1, 4), r.randint(280, 330); ans = p*v/(n*temp); text = f"Using PV=nRT with P={p} kPa, V={v} L, n={n} mol, T={temp} K, compute R' = PV/(nT) in kPa·L/(mol·K)."
        elif t == 1: m, v = r.randint(2, 10), r.randint(3, 15); ans = .5*m*v*v; text = f"What is the kinetic energy in joules of a {m} kg object moving at {v} m/s?"
        elif t == 2:
            half_life = r.randint(2, 9); ans = r.randint(2, 5); time = ans * half_life
            text = f"A substance has a half-life of {half_life} hours. How many half-lives pass in {time} hours?"
        elif t == 3: h = r.randint(1, 4); ans = h; text = f"What is the pH of a solution with hydrogen ion concentration 10^-{h} M?"
        elif t == 4: a, b = r.randint(2, 10), r.randint(2, 10); ans = a+b; text = f"Two resistors of {a} ohm and {b} ohm are in series. Find total resistance."
        elif t == 5: u, g = r.randint(5, 20), 9.8; ans = u*u/(2*g); text = f"Ignoring air resistance, a projectile is launched vertically at {u} m/s. Find its maximum height using g=9.8 m/s²."
        elif t == 6:
            mass, amount = r.randint(18, 180), r.choice([1, 2, 3, 4, 5])
            ans = mass / amount
            text = f"A sample has mass {mass} g and contains {amount} mol. What is its molar mass in g/mol?"
        elif t == 7: c, v = r.randint(1, 5), r.randint(2, 10); ans = c/2; text = f"Dilute a {c} M solution: what amount concentration results when {v} mL is diluted to {v*2} mL?"
        elif t == 8: q, d = r.randint(1, 5), r.randint(1, 10); ans = 8.99e9*q*q/(d*d); text = f"Using k=8.99e9, calculate Coulomb force for charges {q} C separated by {d} m."
        elif t == 9: m, c, dt = r.randint(1, 5), r.randint(2, 8), r.randint(5, 20); ans = m*c*dt; text = f"How much heat is needed for mass {m} kg, specific heat {c} J/(kg·K), and temperature change {dt} K?"
        else: freq = r.randint(4, 9); ans = 6.626e-34 * freq * 1e14; text = f"Using h=6.626e-34 J·s, calculate photon energy for frequency {freq}e14 Hz."
        out.append(Question(f"science-{i+1:02d}", "science", answer_prompt(text), "num", ans, {"template": t}))
    return out
