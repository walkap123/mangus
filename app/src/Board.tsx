import React from 'react';
import { View, Image, StyleSheet } from 'react-native';
import { C } from './theme';

// FEN char -> piece image (uppercase = white, lowercase = black). require()
// paths must be static literals for the Metro bundler.
const PIECES: Record<string, any> = {
  P: require('../assets/pieces/white-pawn.png'),
  N: require('../assets/pieces/white-knight.png'),
  B: require('../assets/pieces/white-bishop.png'),
  R: require('../assets/pieces/white-rook.png'),
  Q: require('../assets/pieces/white-queen.png'),
  K: require('../assets/pieces/white-king.png'),
  p: require('../assets/pieces/black-pawn.png'),
  n: require('../assets/pieces/black-knight.png'),
  b: require('../assets/pieces/black-bishop.png'),
  r: require('../assets/pieces/black-rook.png'),
  q: require('../assets/pieces/black-queen.png'),
  k: require('../assets/pieces/black-king.png'),
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
  highlights?: Record<string, string>; // square -> highlight color
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
          style={[styles.sq, { width: sq, height: sq, backgroundColor: dark ? C.dark : C.light }]}
        >
          {ring ? <View style={[styles.hl, { backgroundColor: ring }]} /> : null}
          {ch ? (
            <Image source={PIECES[ch]} style={{ width: sq * 0.86, height: sq * 0.86 }} resizeMode="contain" />
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
