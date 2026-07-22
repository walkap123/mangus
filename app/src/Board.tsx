import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { C } from './theme';

// Distinct white vs black glyphs — visually different (outline vs filled) even
// if the platform ignores text color on these code points.
const WHITE_G: Record<string, string> = { p: '♙', n: '♘', b: '♗', r: '♖', q: '♕', k: '♔' };
const BLACK_G: Record<string, string> = { p: '♟', n: '♞', b: '♝', r: '♜', q: '♛', k: '♚' };
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
          ]}
        >
          {ring ? <View style={[styles.hl, { backgroundColor: ring }]} /> : null}
          {ch ? (
            (() => {
              const white = ch === ch.toUpperCase();
              return (
                <Text
                  style={{
                    fontSize: sq * 0.82,
                    color: white ? '#f8f8f8' : '#1b1b1b',
                    // contrasting halo so each color reads on any square
                    textShadowColor: white ? 'rgba(0,0,0,0.9)' : 'rgba(255,255,255,0.65)',
                    textShadowOffset: { width: 0, height: 0 },
                    textShadowRadius: 3,
                  }}
                >
                  {(white ? WHITE_G : BLACK_G)[ch.toLowerCase()]}
                </Text>
              );
            })()
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
  hl: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, opacity: 0.5 },
});
