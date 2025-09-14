"use client";

import { useState } from "react";
import {
  Button,
  TextInput,
  Title,
  Container,
  Loader,
  Card,
  Group,
  Text,
  Stack,
  Space,
} from "@mantine/core";
import RemotionVideo from "@/components/RemotionVideo";

export default function HomePage() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [media, setMedia] = useState<{ image: string; video: string } | null>(null);
  const [exporting, setExporting] = useState(false);

  const images = ["/assets/1.jpg", "/assets/2.jpg", "/assets/3.jpg"];
  const videos = ["/assets/v1.mp4", "/assets/v2.mp4", "/assets/v3.mp4"];

  async function handleSubmit() {
    if (!prompt.trim()) return;

    setLoading(true);
    const formData = new FormData();
    formData.append("prompt", prompt);

    try {
      const res = await fetch("http://127.0.0.1:8000/generate", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      if (data.error) {
        alert("Error: " + JSON.stringify(data.error));
        setLoading(false);
        return;
      }
      setResult(data);

      // Pick random image & video
      const randomImage = images[Math.floor(Math.random() * images.length)];
      const randomVideo = videos[Math.floor(Math.random() * videos.length)];
      setMedia({ image: randomImage, video: randomVideo });
    } catch (err) {
      console.error(err);
      alert("Failed to generate. Check backend logs.");
    } finally {
      setLoading(false);
    }
  }

  async function handleExport() {
    if (!result || !media) return;
    setExporting(true);

    // Decide whether to use the selected video or fallback to image; we will choose to use video if available
    const useVideo = !!media.video;

    try {
      const res = await fetch("http://127.0.0.1:8000/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image: media.image,
          video: media.video,
          audio_url: result.audio_url,
          useVideo,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        alert("Export failed: " + text);
        setExporting(false);
        return;
      }

      // Receive blob and trigger download
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "storyshort_output.mp4";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      alert("Export failed: " + err);
    } finally {
      setExporting(false);
    }
  }

  return (
    <Container size="sm" mt="xl">
      {/* Header */}
      <Title order={1} ta="center" mb="lg">
        🎬 Video Generation
      </Title>
      <Text ta="center" c="dimmed" mb="xl">
        Turn your ideas into short narrated videos with subtitles.
      </Text>

      {/* Input Card */}
      <Card shadow="md" padding="lg" radius="md" withBorder>
        <TextInput
          label="Enter your story idea"
          placeholder="e.g., A story about a time-traveling scientist..."
          value={prompt}
          onChange={(e) => setPrompt(e.currentTarget.value)}
          mb="md"
        />

        <Group position="right">
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? <Loader size="sm" color="white" /> : "Generate Video"}
          </Button>
        </Group>
      </Card>

      <Space h="md" />

      {/* Video Preview */}
      {result && media && (
        <Card shadow="sm" padding="lg" radius="md" withBorder mt="xl">
          <Title order={3} mb="md">
            Preview
          </Title>

          <RemotionVideo
            script={result.script}
            audioUrl={`http://127.0.0.1:8000${result.audio_url}`}
            image={media.image}
            video={media.video}
          />

          <Space h="md" />

          <Stack spacing="xs" align="flex-end">
            <Group position="right">
              <Button color="green" onClick={handleExport} disabled={exporting}>
                {exporting ? <Loader size="sm" color="white" /> : "Export & Download Video"}
              </Button>
            </Group>

            <Text size="sm" color="dimmed">
              Tip: The exported video is rendered on the backend using ffmpeg. Make sure ffmpeg is installed
              on the backend host.
            </Text>
          </Stack>
        </Card>
      )}
    </Container>
  );
}
