"use client";

import { useEffect, useState } from "react";
import { Player } from "@remotion/player";
import {
  AbsoluteFill,
  Video,
  Img,
  Audio as RemotionAudio,
  useCurrentFrame,
} from "remotion";

type Props = {
  script: string;
  audioUrl: string;
  image: string;
  video: string;
};

// Subtitles component
const Subtitle = ({
  script,
  fps,
  audioDuration,
}: {
  script: string;
  fps: number;
  audioDuration: number;
}) => {
  const frame = useCurrentFrame();

  const sentences = script.split(/(?<=[.?!])\s+/).filter(Boolean);
  const durationPerSentence = (audioDuration / sentences.length) * fps; // frames per sentence
  const index = Math.floor(frame / durationPerSentence);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 40,
        width: "100%",
        textAlign: "center",
        fontSize: "28px",
        fontWeight: "bold",
        color: "white",
        textShadow: "2px 2px 8px rgba(0,0,0,0.8)",
        padding: "0 20px",
      }}
    >
      {sentences[index] || ""}
    </div>
  );
};

// Composition
const MyComposition = ({
  script,
  audioUrl,
  video,
  image,
  durationInFrames,
  audioDuration,
}: Props & { durationInFrames: number; audioDuration: number }) => {
  const fps = 30;

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {/* Background video (looped) */}
      {video ? (
        <Video
          src={video}
          loop
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      ) : (
        <Img
          src={image}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      )}

      {/* Subtitles */}
      <Subtitle script={script} fps={fps} audioDuration={audioDuration} />

      {/* Audio narration */}
      <RemotionAudio src={audioUrl} />
    </AbsoluteFill>
  );
};

// Remotion Player wrapper
export default function RemotionVideo(props: Props) {
  const [durationInFrames, setDurationInFrames] = useState(300);
  const [audioDuration, setAudioDuration] = useState(10);
  const fps = 30;

  useEffect(() => {
    const audio = new window.Audio(props.audioUrl);
    audio.addEventListener("loadedmetadata", () => {
      const durationSeconds = audio.duration || 10;
      setAudioDuration(durationSeconds);
      setDurationInFrames(Math.ceil(durationSeconds * fps));
    });
  }, [props.audioUrl]);

  return (
    <Player
      component={MyComposition}
      durationInFrames={durationInFrames}
      fps={fps}
      compositionWidth={640}
      compositionHeight={320}
      controls
      inputProps={{ ...props, durationInFrames, audioDuration }}
    />
  );
}
