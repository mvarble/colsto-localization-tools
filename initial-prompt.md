I watched a video in which a guy inferred the location of an audio recording by matching audio dopplers of planes against ADSB data.
I was very impressed with his cuff-rolling data science tricks.
I want to develop upon those skills of tinkering around with data just as he did.
Seeing as I work on very similar problems with radio in L/S/X-band, I thought practicing his exact tools could be useful.

My request to you is to help me discover the tools he is using and understand how to use them myself.
For each tool, I would like you to also help me understand:

- the specific functionality of said tools he uses,
- additional functionality that I may find useful,
- an example of a dataset and a task I may use as a tutorial to introduce myself to the tool and develop an understanding to use it like him.

How I ask you to help me discover the tools is by using `ffmpeg` to grab stills from the video and inspect them.
You also have the subtitles, should this help you give context to the frames.
Try to be conservative with looking at screenshots: don't just inspect every second--if you get a screengrab of what looks like a tool, you probably don't need to look within a vicinity of time.

I will give you help on some of the stills with timeframes in the video.

- 1:01, 4:11, 4:26, 10:46, 11:29, 22:38: looks like some GIS software
- 1:24, 1:37, 1:44: looks like VSCode, but he has some nice set of plots he is able to scroll through, scrub through time, and even change parameters of the spectrogram calculation.
- 7:14, 18:32: looks like some Plotly diagram with a slider
- 9:19, 22:34: looks like some custom site for visually inspecting predicted dopplers against recordings
- 15:17, 15:48: looks again like some custom site for visually interpretting doppler
- 21:31: Again, likely plotly, but he gets checkboxes
- 26:42: Looks like audacity. I suck at using that.

Seeing as I am asking for a lot, please proceed in stages.

1. Read the subtitles to understand his work.
2. Extract the frames and itemize the softwares he uses. Create a markdown file for each software.
3. For each software, think about how he uses it for data inspection, especially in the context of his problem and the stills.
   Populate the respective markdown document with a summary of the software with links to its website, and follow up with a section on how he uses it.
4. Populate each markdown document with tutorial information: first links to existing tutorials--if any really good ones exist--then some tutorials of your own if the links are too simple or don't feel focused enough on the skills I need to learn.
   An example of this is plotly.
   Of course I know it has APIs in numerous languages, but I did not know I could have it be reactive to checkboxes and sliders; don't give me a basic tutorial to plot a line.

If any of his tools look like pedagogical bespoke websites he or AI generated, you can skip them.
Also think about how these tools could be used "quickly" in a data science way.
I already have quite a bit of practice with making bespoke web dashboards for reapeatedly inspecting data of a fixed schema.
I am instead looking to develop the quick-and-dirty skills where I don't know the schema, and I must make plots to explore hypotheses quickly--just as he was able to break the ADSB problem down into parts.
