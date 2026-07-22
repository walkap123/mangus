import React, { useEffect, useRef } from 'react';
import { View, Image, StyleSheet, Animated } from 'react-native';
import { C } from './theme';

// FEN char -> piece image (uppercase = white, lowercase = black).
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

export type Slide = { from: string; to: string } | null;

function fenGrid(fen: string): (string | null)[][] {
  const rows = fen.split(' ')[0].split('/');
  const grid: (string | null)[][] = Array.from({ length: 8 }, () => Array(8).fill(null));
  for (let r = 0; r < 8; r++) {
    let f = 0;
    for (const ch of rows[r]) {
      if (/\d/.test(ch)) f += parseInt(ch, 10);
      else { grid[7 - r][f] = ch; f++; }
    }
  }
  return grid;
}

// A piece that starts at `from` and slides to `to`. Keyed by the move so it
// remounts (and re-initializes) on every ply — no flash at the old spot.
function SlidingPiece({ source, from, to, pieceSize }: {
  source: any; from: { x: number; y: number }; to: { x: number; y: number }; pieceSize: number;
}) {
  const anim = useRef(new Animated.ValueXY(from)).current;
  useEffect(() => {
    Animated.timing(anim, { toValue: to, duration: 160, useNativeDriver: true }).start();
  }, []);
  return (
    <Animated.Image
      source={source}
      resizeMode="contain"
      style={{ position: 'absolute', width: pieceSize, height: pieceSize, left: 0, top: 0,
        transform: anim.getTranslateTransform() }}
    />
  );
}

export function Board({
  fen, flip, size, highlights = {}, slide = null,
}: {
  fen: string; flip: boolean; size: number;
  highlights?: Record<string, string>; slide?: Slide;
}) {
  const sq = size / 8;
  const pieceSize = sq * 0.86;
  const pad = (sq - pieceSize) / 2;
  const grid = fenGrid(fen);

  const coord = (name: string) => {
    const file = name.charCodeAt(0) - 97, rank = +name[1];
    const col = flip ? 7 - file : file, row = flip ? rank - 1 : 8 - rank;
    return { x: col * sq + pad, y: row * sq + pad };
  };

  // square + highlight layer
  const squares = [];
  for (let dr = 0; dr < 8; dr++) {
    const cells = [];
    for (let dc = 0; dc < 8; dc++) {
      const file = flip ? 7 - dc : dc, rank = flip ? dr + 1 : 8 - dr;
      const name = FILES[file] + rank;
      const dark = (file + rank) % 2 === 1;
      const ring = highlights[name];
      cells.push(
        <View key={name} style={[styles.sq, { width: sq, height: sq, backgroundColor: dark ? C.dark : C.light }]}>
          {ring ? <View style={[styles.hl, { backgroundColor: ring }]} /> : null}
        </View>
      );
    }
    squares.push(<View key={dr} style={styles.row}>{cells}</View>);
  }

  // piece layer — everything static except the one piece that slid
  const pieces = [];
  for (let rank = 1; rank <= 8; rank++) {
    for (let file = 0; file < 8; file++) {
      const ch = grid[rank - 1][file];
      if (!ch) continue;
      const name = FILES[file] + rank;
      if (slide && name === slide.to) continue; // drawn by SlidingPiece
      const c = coord(name);
      pieces.push(
        <Image key={name} source={PIECES[ch]} resizeMode="contain"
          style={{ position: 'absolute', width: pieceSize, height: pieceSize, left: c.x, top: c.y }} />
      );
    }
  }

  const slider = (() => {
    if (!slide) return null;
    const f = slide.to.charCodeAt(0) - 97, r = +slide.to[1];
    const ch = grid[r - 1][f];
    if (!ch) return null;
    return (
      <SlidingPiece key={`${slide.from}${slide.to}${fen}`} source={PIECES[ch]}
        from={coord(slide.from)} to={coord(slide.to)} pieceSize={pieceSize} />
    );
  })();

  return (
    <View style={[styles.board, { width: size, height: size }]}>
      {squares}
      <View style={StyleSheet.absoluteFill} pointerEvents="none">
        {pieces}
        {slider}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  board: { borderRadius: 8, overflow: 'hidden' },
  row: { flexDirection: 'row' },
  sq: { alignItems: 'center', justifyContent: 'center' },
  hl: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, opacity: 0.5 },
});
