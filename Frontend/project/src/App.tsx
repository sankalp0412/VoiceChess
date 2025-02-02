import React, { useState } from "react";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";
import {
  Mic,
  MicOff,
  PlayCircle,
  XCircle,
  RotateCcw,
  Clock,
  Trophy,
  Undo,
} from "lucide-react";
import { startGame, playUserMove, endGame, undoMove } from "./services/chessServices";

function App() {
  // The Chess instance (do not recreate from FEN because that would lose history)
  const [game, setGame] = useState(new Chess());
  // Store moves in SAN format (e.g. "e4", "Nf3", etc.)
  const [moveHistory, setMoveHistory] = useState<string[]>([]);
  const [isVoiceEnabled, setIsVoiceEnabled] = useState(false);
  const [gameStarted, setGameStarted] = useState(false);

  /**
   * Rebuild the board by replaying all moves in the provided history.
   */
  const updateGameFromHistory = (history: string[]) => {
    const newGame = new Chess();
    history.forEach((san) => {
      newGame.move(san);
    });
    setGame(newGame);
  };

  /**
   * When Stockfish makes a move, update the moveHistory with the Stockfish SAN,
   * then rebuild the board from the updated history.
   */
  const makeStockfishMove = (stockfish_san: string) => {
    setMoveHistory((prevHistory) => {
      const newHistory = [...prevHistory, stockfish_san];
      updateGameFromHistory(newHistory);
      return newHistory;
    });
  };

  /**
   * Process the user move:
   * - Update the game with the move.
   * - Append the move's SAN to moveHistory.
   * - Call the backend API (playUserMove) which returns Stockfish’s move in SAN.
   * - Update moveHistory with Stockfish’s move.
   */
  async function makeAMove(move: {
    from: string;
    to: string;
    promotion?: string;
  }) {
    try {
      // Make the user move on the current game.
      const result = game.move(move);
      if (!result) return null;

      // Update the move history with the user move.
      setMoveHistory((prev) => {
        const newHistory = [...prev, result.san];
        updateGameFromHistory(newHistory);
        return newHistory;
      });

      // Call the backend to process the user's move.
      // We send the user move's SAN (or you could send other info as needed).
      const response = await playUserMove(result.san);
      console.log("API Response:", response);

      // Extract Stockfish's move in SAN from the response.
      // (Ensure your backend returns the property "stockfish_san".)
      const stockfish_san = response.stockfish_san;
      if (stockfish_san) {
        makeStockfishMove(stockfish_san);
      }

      return result;
    } catch (error) {
      console.error(error);
      return null;
    }
  }

  /**
   * Called when a piece is dropped on the board.
   */
  function onDrop(sourceSquare: string, targetSquare: string) {
    const move = makeAMove({
      from: sourceSquare,
      to: targetSquare,
      promotion: "q",
    });
    return move !== null;
  }

  async function resetGame() {
    setGame(new Chess());
    const response = await endGame();
    console.log(response);
    setGameStarted(false);
    const userEloRatingElement = document.getElementById(
      "userEloRating"
    ) as HTMLInputElement;
    if (userEloRatingElement) userEloRatingElement.value = "";
    setMoveHistory([]);
  }

  const startNewGame = async () => {
    setGameStarted(true);
    const userEloRatingElement = document.getElementById(
      "userEloRating"
    ) as HTMLInputElement;
    let userEloRating = 1200;
    if (userEloRatingElement && userEloRatingElement.value.length) {
      userEloRating = parseInt(userEloRatingElement.value);
    }
    const response = await startGame(userEloRating);
    console.log(response);
  };

  /**
   * Undo the last move by removing it from moveHistory and rebuilding the board.
   */
  async function undoPrevMove() {
    if (moveHistory.length === 0) return; // No moves to undo
  
    // Create a new history by removing the last move
    const newHistory = moveHistory.slice(0, -2);
    updateGameFromHistory(newHistory);
    console.log("History after undo:", newHistory);
  
    // Make API call to undo the move in backend
    try {
      const response = await undoMove(); 
      console.log("Response after undo:", response);
    } catch (error) {
      console.error("Error undoing move:", error);
    }
  
    // Update move history state
    setMoveHistory(newHistory);
  }

  const quitGame = () => {
    if (window.confirm("Are you sure you want to quit the game?")) {
      resetGame();
    }
  };

  const toggleVoice = () => {
    setIsVoiceEnabled(!isVoiceEnabled);
  };
  

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-6xl mx-auto flex gap-8">
        {/* Chess Board Section */}
        <div className="flex-1 bg-white rounded-lg shadow-lg p-6">
          <h1 className="text-3xl font-bold text-gray-800 mb-6">
            Chess with Beth
          </h1>
          <div className="aspect-square max-w-2xl mx-auto">
            <Chessboard
              position={game.fen()}
              onPieceDrop={onDrop}
              boardWidth={560}
              customBoardStyle={{
                borderRadius: "4px",
                boxShadow: "0 2px 10px rgba(0, 0, 0, 0.5)",
              }}
            />
          </div>
        </div>

        {/* Game Controls Section */}
        <div className="w-80 space-y-6">
          {/* Game Status Card */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <Trophy className="text-yellow-500" />
              Game Status
            </h2>
            <div className="space-y-2">
              <p className="text-lg font-medium text-gray-700 flex items-center gap-2">
                <Clock className="text-blue-500" />
                {game.isGameOver()
                  ? "Game Over!"
                  : `${game.turn() === "w" ? "White" : "Black"}'s turn`}
              </p>
              {game.isCheckmate() && (
                <p className="text-xl font-bold text-red-600">
                  Checkmate! {game.turn() === "w" ? "Black" : "White"} wins!
                </p>
              )}
              {game.isDraw() && (
                <p className="text-xl font-bold text-blue-600">Draw!</p>
              )}
            </div>
          </div>

          {/* Game Controls Card */}
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              Game Controls
            </h2>
            <div className="space-y-3">
              <div className="flex space-x-4">
                <button
                  onClick={gameStarted ? quitGame : startNewGame}
                  className={`${
                    gameStarted
                      ? `py-3 rounded-lg bg-red-500 hover:bg-red-600 ${
                          moveHistory.length > 0 ? "w-1/2" : "w-full"
                        }`
                      : "w-full py-3 rounded-lg bg-green-500 hover:bg-green-600"
                  } text-white font-medium flex items-center justify-center gap-2 transition-colors`}
                >
                  {gameStarted ? (
                    <>
                      <XCircle size={20} /> Quit Game
                    </>
                  ) : (
                    <>
                      <PlayCircle size={20} /> Start Game
                    </>
                  )}
                </button>
                {gameStarted && moveHistory.length > 0 && (
                  <button
                    onClick={undoPrevMove}
                    className="w-1/2 py-3 rounded-lg bg-blue-500 hover:bg-blue-600 text-white font-medium flex items-center justify-center gap-2 transition-colors"
                  >
                    <Undo size={20} /> Undo Move
                  </button>
                )}
              </div>
              <input
                id="userEloRating"
                type="text"
                className="w-full py-3 px-4 rounded-lg bg-gray-100 text-gray-800 font-medium"
                placeholder="Enter your ELO rating (default: 1200)"
              />
              <button
                onClick={resetGame}
                className="w-full py-3 bg-blue-500 hover:bg-blue-600 text-white rounded-lg font-medium flex items-center justify-center gap-2 transition-colors"
              >
                <RotateCcw size={20} /> Reset Game
              </button>
              <button
                onClick={toggleVoice}
                className={`w-full py-3 rounded-lg ${
                  isVoiceEnabled
                    ? "bg-green-500 hover:bg-green-600"
                    : "bg-gray-500 hover:bg-gray-600"
                } text-white font-medium flex items-center justify-center gap-2 transition-colors`}
              >
                {isVoiceEnabled ? (
                  <>
                    <Mic size={20} /> Voice Enabled
                  </>
                ) : (
                  <>
                    <MicOff size={20} /> Voice Disabled
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
