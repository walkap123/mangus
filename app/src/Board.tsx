import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { C } from './theme';

const GLYPH: Record<string, string> = {
  p: '♟', n: '♞', b: '♝', r: '♜', q: '♛', k: '♚',
};
const FILES = 'abcdefgh';

function fenGrid(fen: string): (string | null)[][] {
  const rows = fen.split(' ')[0].split('/');
  const grid: (string | null)[][] = Array.from({ length: 8 }, () => Array(8).fill(null));
  for (let r = 0; r < 8; r++) {
    let f = 0;
    for (const ch of rows[r]) {
      if (/\d/.test(ch)) f += parseInt(ch, 10);
      else {
        grid[7 - r][f] = ch;
        f++;
      }
    }
  }
  return grid;
}

export function Board({
  fen,
  flip,
  size,
  highlights = {},
}: {
  fen: string;
  flip: boolean;
  size: number;
  highlights?: Record<string, string>; // square -> ring color
}) {
  const grid = fenGrid(fen);
  const sq = size / 8;
  const rows = [];
  for (let dr = 0; dr < 8; dr++) {
    const cells = [];
    for (let dc = 0; dc < 8; dc++) {
      const file = flip ? 7 - dc : dc;
      const rank = flip ? dr + 1 : 8 - dr;
      const name = FILES[file] + rank;
      const ch = grid[rank - 1][file];
      const dark = (file + rank) % 2 === 1;
      const ring = highlights[name];
      cells.push(
        <View
          key={name}
          style={[
            styles.sq,
            { width: sq, height: sq, backgroundColor: dark ? C.dark : C.light },
            ring ? { borderWidth: 3, borderColor: ring } : null,
          ]}
        >
          {ch ? (
            <Text
              style={[
                styles.pc,
                {
                  fontSize: sq * 0.72,
                  color: ch === ch.toUpperCase() ? '#fff' : '#111',
                },
              ]}
            >
              {GLYPH[ch.toLowerCase()]}
            </Text>
          ) : null}
        </View>
      );
    }
    rows.push(
      <View key={dr} style={styles.row}>
        {cells}
      </View>
    );
  }
  return <View style={[styles.board, { width: size, height: size }]}>{rows}</View>;
}

const styles = StyleSheet.create({
  board: { borderRadius: 8, overflow: 'hidden' },
  row: { flexDirection: 'row' },
  sq: { alignItems: 'center', justifyContent: 'center' },
  pc: { fontWeight: '400', textShadowColor: '#0008', textShadowRadius: 2 },
});
