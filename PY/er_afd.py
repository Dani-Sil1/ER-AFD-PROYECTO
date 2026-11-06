#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
ER-AFD: Convertidor de Expresiones Regulares a Autómatas Finitos Deterministas
Implementación mediante Algoritmo de Thompson + Construcción de Subconjuntos.
Uso: er-afd <ER> <cadena>
"""

import sys
from collections import deque

EPSILON = 'ε'


class Symbol:
    """Representa un símbolo del alfabeto o transición (literal, '.', '[^...]' o 'ε')."""

    def __init__(self, kind: str, display: str, excluded=None):
        self.kind = kind          # 'LIT', 'DOT', 'NEG', 'EPS'
        self.display = display    # Representación en Σ y en la tabla de transiciones
        self.excluded = set(excluded) if excluded else set()

    def matches(self, ch: str) -> bool:
        if self.kind == 'LIT':
            return ch == self.display
        if self.kind == 'DOT':
            return True
        if self.kind == 'NEG':
            return ch not in self.excluded
        return False

    def __eq__(self, other):
        return (
            isinstance(other, Symbol)
            and self.kind == other.kind
            and self.display == other.display
        )

    def __hash__(self):
        return hash((self.kind, self.display))

    def __repr__(self):
        return f"Symbol({self.kind}, {self.display!r})"


# ==============================================================================
# 1. MÓDULO DE ENTRADA DE EXPRESIONES REGULARES (LEXER Y PARSER DESCENDENTE)
# ==============================================================================

def expand_escape_sequence(er: str, i: int):
    r"""
    Procesa secuencias de escape iniciadas con '\' en la posición i:
      - \N   -> [0-9]
      - \A   -> [A-Z]
      - \a   -> [a-z]
      - \z   -> [a-zA-Z]
      - \hXX -> Carácter ASCII en hexadecimal (ej. \h20 = espacio, \h41 = 'A')
      - \x   -> Carácter literal 'x' escapado
    Retorna (lista_de_caracteres, siguiente_indice).
    """
    if i + 1 >= len(er):
        raise ValueError("Secuencia de escape '\\' incompleta al final de la ER.")

    nxt = er[i + 1]
    if nxt == 'N':
        return [chr(c) for c in range(ord('0'), ord('9') + 1)], i + 2
    if nxt == 'A':
        return [chr(c) for c in range(ord('A'), ord('Z') + 1)], i + 2
    if nxt == 'a':
        return [chr(c) for c in range(ord('a'), ord('z') + 1)], i + 2
    if nxt == 'z':
        return (
            [chr(c) for c in range(ord('a'), ord('z') + 1)]
            + [chr(c) for c in range(ord('A'), ord('Z') + 1)]
        ), i + 2
    if nxt == 'h':
        if i + 3 >= len(er):
            raise ValueError("La secuencia \\h requiere dos dígitos hexadecimales (ej. \\h20).")
        hex_code = er[i + 2 : i + 4]
        try:
            ascii_val = int(hex_code, 16)
        except ValueError as exc:
            raise ValueError(f"Código hexadecimal inválido en '\\h{hex_code}'.") from exc
        return [chr(ascii_val)], i + 4

    # Cualquier otro carácter precedido por '\' se interpreta literalmente
    return [nxt], i + 2


def tokenize_regex(er: str):
    """
    Analizador léxico de la expresión regular.
    Retorna:
      - tokens: Lista de tuplas ('SYM', Symbol) o ('OP', operador) con concatenación explícita.
      - sigma_order: Lista de símbolos en orden de aparición en la ER.
      - eps_in_er: Booleano que indica si ε apareció explícitamente en la ER.
    """
    raw_tokens = []
    sigma_order = []
    eps_in_er = False

    def register_symbol(sym: Symbol):
        nonlocal eps_in_er
        if sym.kind == 'EPS':
            eps_in_er = True
        if sym not in sigma_order:
            sigma_order.append(sym)

    i = 0
    n = len(er)
    while i < n:
        ch = er[i]

        if ch == '\\':
            chars, i = expand_escape_sequence(er, i)
            if len(chars) == 1:
                sym = Symbol('LIT', chars[0])
                register_symbol(sym)
                raw_tokens.append(('SYM', sym))
            else:
                # Clases como \N, \A, \a, \z se expanden como unión (c1|c2|...)
                raw_tokens.append(('OP', '('))
                for idx, c in enumerate(chars):
                    if idx > 0:
                        raw_tokens.append(('OP', '|'))
                    sym = Symbol('LIT', c)
                    register_symbol(sym)
                    raw_tokens.append(('SYM', sym))
                raw_tokens.append(('OP', ')'))

        elif ch == '[':
            j = i + 1
            if j >= n:
                raise ValueError("Conjunto '[' sin cerrar.")
            negated = False
            if er[j] == '^':
                negated = True
                j += 1

            set_chars = []
            while j < n and er[j] != ']':
                if er[j] == '\\':
                    echars, j = expand_escape_sequence(er, j)
                    set_chars.extend(echars)
                elif j + 2 < n and er[j + 1] == '-' and er[j + 2] != ']':
                    start_c, end_c = er[j], er[j + 2]
                    if ord(start_c) > ord(end_c):
                        raise ValueError(f"Rango inválido '{start_c}-{end_c}' en conjunto.")
                    for code in range(ord(start_c), ord(end_c) + 1):
                        set_chars.append(chr(code))
                    j += 3
                else:
                    set_chars.append(er[j])
                    j += 1

            if j >= n or er[j] != ']':
                raise ValueError("Conjunto '[' sin cerrar con ']'.")
            if not set_chars:
                raise ValueError("El conjunto '[]' no puede estar vacío.")

            raw_bracket = er[i : j + 1]
            i = j + 1

            if negated:
                sym = Symbol('NEG', raw_bracket, excluded=set_chars)
                register_symbol(sym)
                raw_tokens.append(('SYM', sym))
            else:
                unique_chars = list(dict.fromkeys(set_chars))
                raw_tokens.append(('OP', '('))
                for idx, c in enumerate(unique_chars):
                    if idx > 0:
                        raw_tokens.append(('OP', '|'))
                    sym = Symbol('LIT', c)
                    register_symbol(sym)
                    raw_tokens.append(('SYM', sym))
                raw_tokens.append(('OP', ')'))

        elif ch == '.':
            sym = Symbol('DOT', '.')
            register_symbol(sym)
            raw_tokens.append(('SYM', sym))
            i += 1

        elif ch in ('ε', 'ɛ'):
            sym = Symbol('EPS', EPSILON)
            register_symbol(sym)
            raw_tokens.append(('SYM', sym))
            i += 1

        elif ch in ('*', '|', '(', ')'):
            raw_tokens.append(('OP', ch))
            i += 1

        else:
            sym = Symbol('LIT', ch)
            register_symbol(sym)
            raw_tokens.append(('SYM', sym))
            i += 1

    # Insertar operador explícito de concatenación ('OP', 'CONCAT')
    tokens = []
    for idx, tok in enumerate(raw_tokens):
        if idx > 0:
            prev = raw_tokens[idx - 1]
            prev_can_end = (prev[0] == 'SYM') or (prev == ('OP', '*')) or (prev == ('OP', ')'))
            curr_can_start = (tok[0] == 'SYM') or (tok == ('OP', '('))
            if prev_can_end and curr_can_start:
                tokens.append(('OP', 'CONCAT'))
        tokens.append(tok)

    return tokens, sigma_order, eps_in_er


# Nodos del Árbol de Sintaxis Abstracta (AST)
class ASTNode:
    pass


class SymbolNode(ASTNode):
    def __init__(self, symbol: Symbol):
        self.symbol = symbol


class ConcatNode(ASTNode):
    def __init__(self, left: ASTNode, right: ASTNode):
        self.left = left
        self.right = right


class UnionNode(ASTNode):
    def __init__(self, left: ASTNode, right: ASTNode):
        self.left = left
        self.right = right


class StarNode(ASTNode):
    def __init__(self, child: ASTNode):
        self.child = child


class RecursiveDescentParser:
    """
    Parser descendente recursivo para validar la sintaxis de la ER y construir el AST.
    Gramática:
      expr   -> term ('|' term)*
      term   -> factor ('CONCAT' factor)*
      factor -> base ('*')*
      base   -> SYM | '(' expr ')'
    """

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self, expected_type=None, expected_val=None):
        tok = self.current()
        if tok is None:
            raise ValueError("Expresión regular incompleta.")
        if expected_type and tok[0] != expected_type:
            raise ValueError(f"Error de sintaxis: se esperaba {expected_type}, se encontró {tok[1]}.")
        if expected_val and tok[1] != expected_val:
            raise ValueError(f"Error de sintaxis: se esperaba '{expected_val}', se encontró '{tok[1]}'.")
        self.pos += 1
        return tok

    def parse(self) -> ASTNode:
        if not self.tokens:
            raise ValueError("La expresión regular no puede estar vacía.")
        node = self.parse_expr()
        if self.current() is not None:
            raise ValueError(f"Error de sintaxis: token inesperado '{self.current()[1]}'.")
        return node

    def parse_expr(self) -> ASTNode:
        node = self.parse_term()
        while self.current() == ('OP', '|'):
            self.consume('OP', '|')
            right = self.parse_term()
            node = UnionNode(node, right)
        return node

    def parse_term(self) -> ASTNode:
        node = self.parse_factor()
        while self.current() == ('OP', 'CONCAT'):
            self.consume('OP', 'CONCAT')
            right = self.parse_factor()
            node = ConcatNode(node, right)
        return node

    def parse_factor(self) -> ASTNode:
        node = self.parse_base()
        while self.current() == ('OP', '*'):
            self.consume('OP', '*')
            node = StarNode(node)
        return node

    def parse_base(self) -> ASTNode:
        tok = self.current()
        if tok is None:
            raise ValueError("Error de sintaxis: se esperaba un operando o '('.")
        if tok[0] == 'SYM':
            self.consume('SYM')
            return SymbolNode(tok[1])
        if tok == ('OP', '('):
            self.consume('OP', '(')
            if self.current() == ('OP', ')'):
                raise ValueError("Error de sintaxis: paréntesis vacíos '()'.")
            node = self.parse_expr()
            self.consume('OP', ')')
            return node
        raise ValueError(f"Error de sintaxis: operador inesperado '{tok[1]}'.")


# ==============================================================================
# 2. MÓDULO DE CONVERSIÓN A AFND (THOMPSON) Y AFD (SUBCONJUNTOS)
# ==============================================================================

class AFND:
    def __init__(self, num_states, start_state, accept_state, transitions, sigma):
        self.num_states = num_states
        self.start_state = start_state
        self.accept_state = accept_state
        self.transitions = transitions  # dict: (estado_int, Symbol) -> set(estados_int)
        self.sigma = sigma              # list[Symbol]


class AFD:
    def __init__(self, num_states, start_state, accept_states, transitions, sigma, subsets):
        self.num_states = num_states
        self.start_state = start_state
        self.accept_states = accept_states  # list[int]
        self.transitions = transitions      # dict: (Q_int, Symbol) -> Q_dest_int
        self.sigma = sigma                  # list[Symbol]
        self.subsets = subsets              # list[frozenset[int]]


def build_thompson_afnd(ast: ASTNode, sigma_order: list, eps_in_er: bool) -> AFND:
    """
    Construye el AFND mediante el algoritmo de Thompson, asignando estados
    correlativos q0, q1, ..., qn donde q0 es el estado inicial.
    """
    next_state_id = 0
    transitions = {}
    eps_sym = Symbol('EPS', EPSILON)

    def new_state() -> int:
        nonlocal next_state_id
        s = next_state_id
        next_state_id += 1
        return s

    def add_edge(u: int, sym: Symbol, v: int):
        transitions.setdefault((u, sym), set()).add(v)

    def build(node: ASTNode, start_s: int) -> int:
        if isinstance(node, SymbolNode):
            end_s = new_state()
            add_edge(start_s, node.symbol, end_s)
            return end_s

        if isinstance(node, ConcatNode):
            mid_s = build(node.left, start_s)
            end_s = build(node.right, mid_s)
            return end_s

        if isinstance(node, UnionNode):
            left_start = new_state()
            left_end = build(node.left, left_start)
            right_start = new_state()
            right_end = build(node.right, right_start)
            end_s = new_state()
            add_edge(start_s, eps_sym, left_start)
            add_edge(start_s, eps_sym, right_start)
            add_edge(left_end, eps_sym, end_s)
            add_edge(right_end, eps_sym, end_s)
            return end_s

        if isinstance(node, StarNode):
            inner_start = new_state()
            inner_end = build(node.child, inner_start)
            end_s = new_state()
            add_edge(start_s, eps_sym, inner_start)
            add_edge(start_s, eps_sym, end_s)
            add_edge(inner_end, eps_sym, inner_start)
            add_edge(inner_end, eps_sym, end_s)
            return end_s

        raise ValueError(f"Tipo de nodo AST no soportado: {type(node)}")

    q0 = new_state()
    qf = build(ast, q0)

    # Si ε no apareció en la ER, se agrega al final de Σ en el AFND según la especificación
    afnd_sigma = list(sigma_order)
    if not eps_in_er:
        afnd_sigma.append(eps_sym)

    return AFND(next_state_id, q0, qf, transitions, afnd_sigma)


def build_subset_afd(afnd: AFND) -> AFD:
    """
    Transforma el AFND en un AFD utilizando el algoritmo de Construcción de Subconjuntos.
    Los estados se numeran correlativamente Q0, Q1, ..., Qm donde Q0 es el inicial.
    """
    eps_sym = Symbol('EPS', EPSILON)
    afd_sigma = [s for s in afnd.sigma if s.kind != 'EPS']

    def eps_closure(states) -> frozenset:
        stack = list(states)
        closure = set(states)
        while stack:
            u = stack.pop()
            for v in afnd.transitions.get((u, eps_sym), ()):
                if v not in closure:
                    closure.add(v)
                    stack.append(v)
        return frozenset(closure)

    def move(states, sym: Symbol) -> frozenset:
        direct = set()
        for u in states:
            for v in afnd.transitions.get((u, sym), ()):
                direct.add(v)

        # Si el subconjunto tiene una transición explícita para el símbolo 'sym' y además
        # posee transiciones comodín ('.' o '[^...]') activas en el mismo subconjunto,
        # se unifican los destinos para preservar el determinismo (ej. en patrones como ".*a").
        if direct and sym.kind == 'LIT':
            for u in states:
                for (st, edge_sym), dests in afnd.transitions.items():
                    if st == u and edge_sym.kind in ('DOT', 'NEG') and edge_sym.matches(sym.display):
                        direct.update(dests)
        elif direct and sym.kind == 'NEG':
            for u in states:
                for (st, edge_sym), dests in afnd.transitions.items():
                    if st == u and edge_sym.kind == 'DOT':
                        direct.update(dests)

        return frozenset(direct)

    q0_closure = eps_closure({afnd.start_state})
    subsets = [q0_closure]
    subset_to_id = {q0_closure: 0}
    queue = deque([q0_closure])
    afd_transitions = {}

    while queue:
        curr_subset = queue.popleft()
        curr_id = subset_to_id[curr_subset]

        for sym in afd_sigma:
            next_nfa_states = move(curr_subset, sym)
            if not next_nfa_states:
                continue
            next_subset = eps_closure(next_nfa_states)
            if next_subset not in subset_to_id:
                subset_to_id[next_subset] = len(subsets)
                subsets.append(next_subset)
                queue.append(next_subset)
            afd_transitions[(curr_id, sym)] = subset_to_id[next_subset]

    accept_states = [
        idx for idx, sub in enumerate(subsets)
        if afnd.accept_state in sub
    ]

    return AFD(
        num_states=len(subsets),
        start_state=0,
        accept_states=accept_states,
        transitions=afd_transitions,
        sigma=afd_sigma,
        subsets=subsets,
    )


def format_afnd(afnd: AFND) -> str:
    """Genera la representación en texto de la tabla de transiciones del AFND."""
    lines = ["AFND"]
    q_list = ",".join(f"q{i}" for i in range(afnd.num_states))
    sigma_list = ",".join(s.display for s in afnd.sigma)
    lines.append(f"Q={{{q_list}}}")
    lines.append(f"Σ={{{sigma_list}}}")
    lines.append(f"F={{q{afnd.accept_state}}}")

    for s in range(afnd.num_states):
        for sym in afnd.sigma:
            dests = afnd.transitions.get((s, sym))
            if dests:
                dest_str = ",".join(f"q{d}" for d in sorted(dests))
                lines.append(f"q{s}|{sym.display}|{{{dest_str}}}")
    return "\n".join(lines)


def format_afd(afd: AFD) -> str:
    """Genera la representación en texto de la tabla de transiciones del AFD."""
    lines = ["AFD"]
    q_list = ",".join(f"Q{i}" for i in range(afd.num_states))
    sigma_list = ",".join(s.display for s in afd.sigma)
    f_list = ",".join(f"Q{i}" for i in afd.accept_states)
    lines.append(f"Q={{{q_list}}}")
    lines.append(f"Σ={{{sigma_list}}}")
    lines.append(f"F={{{f_list}}}")

    for s in range(afd.num_states):
        for sym in afd.sigma:
            if (s, sym) in afd.transitions:
                dest = afd.transitions[(s, sym)]
                lines.append(f"Q{s}|{sym.display}|Q{dest}")
    return "\n".join(lines)


# ==============================================================================
# 3. MÓDULO DE ANÁLISIS DE ENTRADA
# ==============================================================================

def unescape_input_string(raw_str: str) -> str:
    """Procesa espacios escapados ('\\ ') en la cadena de entrada si se pasan entre comillas."""
    out = []
    i = 0
    while i < len(raw_str):
        if raw_str[i] == '\\' and i + 1 < len(raw_str) and raw_str[i + 1] == ' ':
            out.append(' ')
            i += 2
        else:
            out.append(raw_str[i])
            i += 1
    return "".join(out)


def evaluate_string(afd: AFD, cadena: str):
    """
    Evalúa la cadena de entrada sobre el AFD construido.
    Retorna (aceptada: bool, pasos: list[(estado_actual, caracter, estado_siguiente)]).
    """
    curr_state = afd.start_state
    steps = []

    for ch in cadena:
        next_state = None
        lit_sym = Symbol('LIT', ch)

        # 1. Buscar transición exacta con el símbolo literal
        if (curr_state, lit_sym) in afd.transitions:
            next_state = afd.transitions[(curr_state, lit_sym)]
        else:
            # 2. Buscar transición mediante conjunto negativo [^...] o comodín '.'
            for sym in afd.sigma:
                if sym.kind in ('NEG', 'DOT') and (curr_state, sym) in afd.transitions:
                    if sym.matches(ch):
                        next_state = afd.transitions[(curr_state, sym)]
                        break

        if next_state is None:
            return False, steps

        steps.append((curr_state, ch, next_state))
        curr_state = next_state

    accepted = curr_state in afd.accept_states
    return accepted, steps


def run_cli(er_arg: str, cadena_arg: str) -> int:
    """Ejecuta el flujo completo e imprime las tablas y el recorrido. Retorna 1 (aceptada) o 0 (rechazada)."""
    tokens, sigma_order, eps_in_er = tokenize_regex(er_arg)
    ast = RecursiveDescentParser(tokens).parse()

    afnd = build_thompson_afnd(ast, sigma_order, eps_in_er)
    afd = build_subset_afd(afnd)

    print(format_afnd(afnd))
    print()
    print(format_afd(afd))
    print()

    cadena = unescape_input_string(cadena_arg)
    accepted, steps = evaluate_string(afd, cadena)

    for q_curr, ch, q_next in steps:
        print(f"Q{q_curr}|{ch}|Q{q_next}")

    if accepted:
        print("Cadena aceptada")
        return 1
    else:
        print("Cadena rechazada")
        return 0


def main():
    if len(sys.argv) < 3:
        print("Uso: er-afd <ER> <cadena>", file=sys.stderr)
        sys.exit(0)

    er_arg = sys.argv[1]
    cadena_arg = sys.argv[2]

    try:
        exit_code = run_cli(er_arg, cadena_arg)
    except ValueError as err:
        print(f"Error en la expresión regular: {err}", file=sys.stderr)
        sys.exit(0)

    # La especificación requiere retornar código 1 para aceptada y 0 para rechazada
    sys.exit(exit_code)


if __name__ == "__main__":
    main()