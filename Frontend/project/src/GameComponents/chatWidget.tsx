import { useEffect, useState } from "react";
import { MessageCircle, X } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { BotMessageSquare } from "lucide-react";

import { useAiAnalysisMutation } from "@/services/hooks";
import { Typewriter } from "react-simple-typewriter";
import useGameStore from "@/hooks/useGameStore";

const ChatWidget: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [message, setMessage] = useState("");
  const { mutate: aiAnalysis, isPending, isError } = useAiAnalysisMutation();
  const { gameId } = useGameStore();
  const handleTalkToBeth = async () => {
    setMessage("");
    aiAnalysis(
      { game_id: gameId },
      {
        onSuccess: (data) => {
          // console.log(data);
          setMessage(data.analysis);
        },
        onError: (error) => {
          console.error(`Error while fetching analysis : ${error}`);
        },
      }
    );
  };

  useEffect(() => {
    if (isOpen) {
      setMessage("");
    }
  }, [isOpen]);

  return (
    <div className="relative h-full w-full">
      {/* Floating Button */}
      {!isOpen && (
        <Button
          className="flex items-center gap-2 p-3 rounded-full shadow-lg bg-blue-600 text-white"
          onClick={() => setIsOpen(true)}
        >
          <MessageCircle size={20} />
          <span className="hidden sm:block">Need Help? Ask Beth!</span>
        </Button>
      )}

      {/* Chat Window */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            key="beth"
            exit={{ opacity: 0, y: -50, transition: { duration: 0.3 } }}
            initial={{ opacity: 0, y: -10, scale: 1, x: 0 }}
            animate={{ opacity: 1, y: 0, transition: { duration: 0.5 } }}
          >
            <Card className="w-full h-full p-3 shadow-xl bg-white">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-bold">Ask Beth</h3>
                <X
                  className="cursor-pointer"
                  onClick={() => setIsOpen(false)}
                />
              </div>
              <CardContent className="h-48 overflow-y-auto border-t mt-2 p-2">
                {isPending ? (
                  <div className="flex flex-col items-center justify-center text-gray-500 space-y-4 mt-10">
                    <div className="loader border-t-4 border-blue-500 rounded-full w-10 h-10 animate-spin"></div>
                    <Typewriter
                      words={[
                        "Studying position...",
                        "Analyzing moves...",
                        "Evaluating scores...",
                      ]}
                      loop={false}
                      typeSpeed={50}
                    />
                  </div>
                ) : isError ? (
                  <div className="text-red-500 text-center mt-10">
                    Oops! Something went wrong. Please try again.
                  </div>
                ) : (
                  <div className="flex">
                    <BotMessageSquare className="mr-2" />
                    <motion.p
                      className="text-gray-500"
                      style={{ whiteSpace: "pre-wrap" }}
                      initial={{ width: 0 }}
                      animate={{ width: "100%" }}
                      transition={{ duration: 1, ease: "easeInOut" }}
                    >
                      {message.length > 0
                        ? message
                        : "Hi, I’m GM Beth! let’s sharpen your chess skills!"}
                    </motion.p>
                  </div>
                )}
              </CardContent>
              <div className="flex justify-center mt-2">
                <Button onClick={handleTalkToBeth} disabled={isPending}>
                  {isPending ? "Fetching analysis..." : "What should I do?"}
                </Button>
              </div>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ChatWidget;
