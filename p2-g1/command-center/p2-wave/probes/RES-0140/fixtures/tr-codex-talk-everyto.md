---
title: "Transcript: 'How OpenAI’s Codex Team Uses Their Coding Agent'"
subtitle: ‘AI & I’ with Thibault Sottiaux and Andrew Ambrosino
description: ‘AI & I’ with Thibault Sottiaux and Andrew Ambrosino
authors: [Dan Shipper]
publication: AI & I
publication_slug: podcast
published_at: "2026-02-18T07:00:00.000-05:00"
canonical_url: "https://every.to/podcast/transcript-how-openai-s-codex-team-uses-their-coding-agent"
audience: everyone
slug: transcript-how-openai-s-codex-team-uses-their-coding-agent
---
**The transcript of _[AI & I](https://every.to/podcast)_ with OpenAI’s Thibault Sottiaux and Andrew Ambrosino is below. Watch on [X](https://x.com/danshipper/status/2024187698970300809) or [YouTube](https://youtu.be/AFHiiL-ZKms), or listen on [Spotify](https://open.spotify.com/episode/6bVrjHG2evanjiXgM1UNDF?si=7AHAxh-0RoGRQUuJA_yfPg) or [Apple Podcasts](https://podcasts.apple.com/us/podcast/openais-codex-this-model-is-so-fast-it-changes-how-you-code/id1719789201?i=1000750353718).**

### **Timestamps**

-
Introduction: 00:01:27

-
OpenAI’s evolving bet on its coding agent: 00:05:27

-
The choice to invest in a GUI (over a terminal): 00:09:42

-
The AI workflows that the Codex team relies on to ship: 00:20:38

-
Teaching Codex how to read between the lines: 00:26:45

-
Building affordances for a lightning-fast model: 00:28:45

-
Why speed is a dimension of intelligence: 00:33:15

-
Code review is the next bottleneck for coding agents: 00:36:30

-
How the Codex team positions itself against the competition: 00:41:24

### **Transcript**

**(00:00:00)**

**Dan Shipper**

Thibault. Andrew. Welcome to the show.

**Thibault Sottiaux**

Hey. Thanks for having us.

**Andrew Ambrosino**

Thanks for having us.

**Dan Shipper**

Great to get to chat with you. So for people who don’t know, Thibault, you are the head of Codex at OpenAI, and Andrew, you are a member of the technical staff on the Codex app at OpenAI. And you are the people of the moment. They just ran a Super Bowl commercial about Codex. How are you feeling?

**Thibault Sottiaux**

Yeah, that Super Bowl ad was quite surprising, wasn’t it?

**Dan Shipper**

It really was. I think the core thing, and the reason I want to start the conversation here, is it feels like a strategic shift. You would expect OpenAI to have run a ChatGPT commercial during the Super Bowl, and maybe not—especially if you looked at Codex’s positioning three or four months ago for professional engineers—to have run an ad targeted at a much broader audience. For a long time there was this divide where Codex was for professional engineers and if you want to do vibe coding, you do that in the ChatGPT app. It seems like that has shifted a lot over the last month or two. Can you tell me about that?

**Thibault Sottiaux**

Yeah, I think especially—we can talk about last week, right? So last week on Monday we released a Codex app. Immediately we saw a ton of downloads, more than a million downloads in the first week. And then we knew that we were releasing an extremely strong model, o3 Codex, on Thursday. That just made it very visible that we’re here to put incredible experiences out there. We’re very committed to Codex, and agents are really starting to work and be able to create these things, even if you’re a little bit less technical.

I think the app really showed that it’s much more inviting for people to just try it, run multiple agents. With our models being very good at allowing for multitasking and being reliable for long-running sessions, it allows you to create a lot more. So it just felt like maybe we can inspire more people to build and show that agents are here. It’s not coming—it’s going to be mainstream. Why don’t you try and create something new and inspire people? That felt like the right thing we wanted to reinforce.

**Dan Shipper**

Great to get to chat with you. So for people who don’t know, Thibault, you are the head of Codex at OpenAI, and Andrew, you are a member of the technical staff on the Codex app at OpenAI. And you are the people of the moment. They just ran a Super Bowl commercial about Codex. How are you feeling?

**Thibault Sottiaux**

Yeah, that Super Bowl ad was quite surprising, wasn’t it?

**Dan Shipper**

It really was. I think the core thing, and the reason I want to start this conversation here, is it feels like a strategic shift. You would expect OpenAI to have run a ChatGPT commercial during the Super Bowl, and maybe not—especially if you looked at Codex’s positioning three or four months ago for professional engineers—have run an ad targeted at a much broader audience. For a long time there was this divide where Codex was for professional engineers and if you want to do vibe coding, you do that in the ChatGPT app. It seems like that has shifted a lot over the last month or two. Can you tell me about that?

**Thibault Sottiaux**

Yeah, I think especially—we can talk about last week, right? So last week on Monday we released a Codex app. Immediately we saw a ton of downloads, more than a million downloads in the first week. And then we knew that we were releasing an extremely strong model, O3 Codex, on Thursday. That just made it very visible that we’re here to put incredible experiences out there. We’re very committed to Codex, and agents are really starting to work and be able to create these things, even if you’re a little bit less technical.

I think the app really showed that it’s much more inviting for people to just try it, run multiple agents. With our models being very good at allowing for multitasking and being reliable for long-running sessions, it allows you to create a lot more. So it just felt like maybe we can inspire more people to build and show that agents are here. It’s not coming—it’s going to be mainstream. Why don’t you try and create something new and inspire people? That felt like the right thing we wanted to reinforce.

**Andrew Ambrosino**

Yeah. While we were designing and developing the app, one of our internal mandates to ourselves the whole time was that we had to make something that we love to use and that we used for all of our work. And if we couldn’t do that, then we weren’t going to put this out. This was back when we started. And I think we surprised ourselves a lot with how fun it was.

Especially as we started to build this app before we started to build agent skills. And then once we kind of paired them together, it became this really rich, interactive experience where you could open the browser or connect to various services. All of a sudden we started to feel this really connected, interactive experience and wanted to share. I kind of see the ad as a love letter to builders. I have never seen a Linux CD in a Super Bowl ad. That was really cool to watch.

**Dan Shipper**

What was the impact of the ad?

**Thibault Sottiaux**

We’re still measuring that. We’ll see how it plays out over the long term, but we saw a giant surge of traffic—remarkably, very quickly after 4:00 p.m. PST when it aired. Our systems were under heavy load. It felt kind of weird to me. People are watching the Super Bowl and then going and installing the app and trying it out right there. But that happened. A lot of people reached out saying they were really inspired by it and just wanted to build afterwards, which is what we’re aiming for.

**Dan Shipper**

I still want to talk a little bit about the strategic shift. Codex app moving from, or Codex in general, moving from something that is really for professional developers to something that has a broader audience. And maybe moving some of the vibe coding from ChatGPT into the Codex app. Tell me about that.

**Thibault Sottiaux**

I don’t think we’re trying to move vibe coding from ChatGPT into the Codex app. Two things are happening. One, we’re pushing the frontier on professional software development. O3 Codex beats every single other model on the top benchmarks for coding. It is a very, very capable model, and at the speed and cost, it is a top performer.

The second thing is the app does make things more accessible, so it does appeal to a wider audience. But internally we’re also seeing the app used within research, within our own team. The entire Codex team uses the app. It makes people more productive. So we’re very much leaning into how we think agents are best used—the patterns that we’re seeing that are making people very productive here at the company and outside. And then just going all in on that.

It does happen that at the same time, delegation is finally here. It works. It’s much more accessible, and we’re going to try and see how we can package that and ship it to a much wider audience. But that might not be the Codex app. I mean, you use it all day. You just build in there.

**Andrew Ambrosino**

99 percent of the code that I write is using the Codex app.

**Thibault Sottiaux**

Same. I live there now.

**Dan Shipper**

Okay, well that’s actually really interesting. I definitely want to talk about the app in particular, but I want to go back to the thing you just said. Maybe if I’m reading you right, you’re kind of like, we’re pushing the frontier, we’re seeing lots of people who are maybe broader than just senior engineers using this. However, the overall idea of who is doing what in which app—maybe you haven’t totally figured out yet. It’s not as clean of a line as “no longer vibe coding in ChatGPT” or “really vibe coding in Codex.” You can do it in both, but you haven’t figured out exactly which thing you’re going to do where.

**Thibault Sottiaux**

Yeah, I think Codex is the most powerful experience out there right now. You should be fairly technical so that you understand that code is actually getting written and it’s going to get executed on your machine—though it fully executes in the sandbox. But you should probably be able to read code in order to use Codex to its fullest.

We will bring a similar experience to ChatGPT at some point, which will have different properties in terms of the sandbox and how concepts are represented. Maybe we won’t be showing this scary terminal command thing running that you should probably approve. You shouldn’t do that to someone who is not technical. Codex is really there to appeal to all coders, builders, technical people who are either technical themselves or technically adjacent—data science, those kinds of things.

**Andrew Ambrosino**

Yeah. If you use the Codex app for any amount of time, you can see the inspirations from chat. The layout’s very similar. We auto-name your conversations, we’ve got contextual actions, but it’s pretty clean. The composer looks very similar. And you’ll see some of that inspiration back in chat for other types of things.

But we still believe that when we set out to make something for the professional software developer and for us, it deserved a dedicated experience that could really showcase the power of the models and the way that the models could change the development life cycle. So we made something very tailored to that. We’ve had a lot of success internally with research teams, with product teams. We’ll look beyond, but I think we’re really happy with where we’ve ended up on the tailored approach to this.

**Dan Shipper**

Can you tell me about the decision to invest in a GUI over a CLI? I feel like CLIs are so hot right now, and obviously you have one for Codex already. You could have said, okay, we’re going to double down and just make the terminal experience even better than it is now and really invest in that vs. okay, we’re going to make a GUI—which is a little bit counterintuitive or counter-narrative. Tell me about that decision process.

**Thibault Sottiaux**

I think it wasn’t counterintuitive. It’s more that maybe it’s not mainstream. We experiment with a lot of different approaches. I very much consider that we’re still in the experimentation phase.

We’re responsible primarily for two things. One is building the most powerful entity out there that’s capable of coding. Increasingly this will become a multi-agent system and it’ll become more and more capable. You’ll have to figure out how to steer and supervise its outcome and its behavior. That’s one thing we’re building.

And then we’re also building how do you even interact with this? What is the optimal way to have visibility into what this very capable entity or system of entities is doing? How do you steer them? How do you supervise them?

We are very much still experimenting with what that is. Sure, you can do it in the CLI. At some point it starts to feel very limiting, especially on multimodal stuff. The models can draw little diagrams and generate images, or you can talk over it using voice. Maybe you have many of them going in parallel and you start to lose track. So we felt like we needed to start experimenting with something else.

It was only when we saw it become super popular internally that we were like, we have to ship this externally. This has come to a point where it’s too good to just keep it to ourselves. That was the journey. You were building the app, and when did you start building the app? That was actually fairly quickly—the app was building itself.

**(00:10:00)**

**Andrew Ambrosino**

That was pretty quickly, yeah. I was starting with the CLI and the IDE extension. My goal personally was to get to fully building the app on the app as fast as possible. It’s really easy when building this stuff to slip into thinking “this will be good for somebody.” We really wanted to get to: I want to build the app on the app, I want it to run itself with skills, I want it to click around on the app that it spawned, and I want this to be part of my workflow as soon as possible.

I still use the CLI sometimes when I want to fire something quick. But there’s something about the flexibility of controlling the UI—having some panes be persistent and others be ephemeral. We shipped voice with the app, so you can prompt with voice. We have mermaid diagrams, full image rendering. All of those things are the tip of the iceberg for what we want to do with a dedicated UI. It’s pretty simple, intentionally so, but we’re going to do a lot with dynamic stuff there.

**Thibault Sottiaux**

The ceiling is just much higher.

**Dan Shipper**

My experience trying the app—I didn’t really want to go back to a terminal. I had been coding mostly in Claude Code and some Codex in the terminal for several months before that. What I realized is that GUIs are great. IDEs are just the problem. There’s something that’s a GUI for programming that’s not an IDE, and it seems like you’re figuring that out. I don’t even know what that’s called.

**Thibault Sottiaux**

It’s called the Codex app.

**Andrew Ambrosino**

There was a moment during development where everybody and their mother was forking the same IDE. We looked at each other and were like, should we have done a fork of VS Code as well? Very seriously. I remember exactly which day it was. I wouldn’t say IDEs are the problem, but I go back to the truck analogy sometimes. I’ll open an IDE here and there—I opened one today for something specific—but then I closed it and went back to the Codex app.

The Codex app should be your daily driver. Occasionally you need an IDE or a really complex terminal setup, but this should be your home base, your command center for the agents that are running, a place you can come back to and track everything.

We had a lot of design decisions around whether to allow freeform panels like an IDE. We concluded that what these models are great at is knowing what’s needed in the moment for a given task. So we wanted more control over what shows at what point. You can see that in plan mode—you’re not getting a composer, you’re getting a quick way to answer questions. You’ve got your plan and you can edit it. We want to do more with that.

**Thibault Sottiaux**

It seems like you were surprised you didn’t want to go back to the CLI.

**Dan Shipper**

I was.

**Andrew Ambrosino**

Were you a CLI power user? Greg did an interview where he said, I’m a CLI power user, I thought I would never leave the terminal.

**Thibault Sottiaux**

Greg lives in Emacs.

**Dan Shipper**

I was a CLI power user for about six months, starting when Claude Code first got really good. I thought it was so much better than Cursor or Windsurf. Now I feel like I speed-ran my CLI era and I’m back in GUIs. I’m flipping back and forth, but I can see the light—especially if you have a bunch of agents going at once, the affordances of a GUI just make it much nicer.

**Thibault Sottiaux**

There’s a lot more to come. It was very intentional. Agents are already acting on much more than code. They need to be a companion through every app and everything you do on your computer. We integrate with Linear, Slack. They need to read and produce code, but maybe they can also do deploys or Vercel. Are you going to do all that from an IDE? That would feel odd.

It’s a command center for your agent. We optimize the experience around the idea that you have a very capable, intelligent entity that you’re controlling, steering, and supervising. You never need to do the things yourself—the thing is very capable of being delegated to. When you accept that’s where we’re headed, and with O3 Codex it feels like we’re almost there, it’s the same as working with you. When I talk to you about a feature idea, you get inspired and go do it. I don’t jump into your IDE and implement it myself.

**Andrew Ambrosino**

You could.

**Thibault Sottiaux**

I think you would find it disturbing. That’s how everyone will work with agents. You just talk to them.

**Dan Shipper**

How has your workflow changed with O3 Codex versus O2?

**Thibault Sottiaux**

I was surprised at how much faster it was. I had to adjust. I’d been optimizing for long-running, multitasking workflows—this task will take 10 or 15 minutes, I’ll kick off four different things and come back. Now I can do less multitasking and stay more in the flow. That felt really good.

It also feels satisfying to kick off automations using skills. It’s a more generally capable model, less narrowly focused on code. I find it much more reliable for things like going through Twitter replies and summarizing important themes, or filing bugs in Linear and using automation so things get implemented daily. It’s much more robust for those tasks. But Andrew is the superpower user here. I have very vanilla usage compared to him.

**Andrew Ambrosino**

I had a series I intended to run for a while but only did for three days on X. I was setting up a prompt to add a random, non-shippable feature to the Codex app, with a long prompt about the quality bar. Once I switched to O3 Codex, the results got much more interesting. We did a Subway Surfers panel on the right. A Minecraft UI for the sub-agents. Maybe we’ll ship it.

**Thibault Sottiaux**

I was like, get back to work.

**Andrew Ambrosino**

You’ve got to explore. O3 Codex is neat, fast, capable, multimodal.

**Dan Shipper**

Thibault says you have a lot of cool use cases. What are the more interesting ways you’re using the Codex app that people should try but haven’t thought of?

**Thibault Sottiaux**

Andrew came up with automations. It shifts how you think about things when you can run something in the background on a specific trigger or at a specific time and program it yourself.

**Andrew Ambrosino**

I use the app for a lot of things outside of just coding features. I use it to keep my PRs mergeable with automations—it resolves merge conflicts, keeps them updated, fixes build issues. As soon as they’re ready to go, they’re ready to go. No more “somebody merged a big thing and now there’s a conflict.”

**(00:20:00)**

**Dan Shipper**

So at what point does the automation trigger? I thought automations triggered on a time schedule, but it sounds like there are other triggers I didn’t know about.

**Andrew Ambrosino**

We’re looking at a lot of things. Right now I have it on a time schedule. I use our GitHub skill and some internal skills for our CI. It runs hourly or every two hours and just cleans everything up.

**Dan Shipper**

So it looks through any changes on main, checks any PRs, and makes sure they’re all up to date so whenever you’re ready to go, you’re good. That’s actually really helpful.

**Andrew Ambrosino**

It’s surprisingly helpful. I also have one that every day at 9 AM sends me all the contributions that merged to the Codex app over the last day. It does a nice report of who merged what, grouped by theme, so I can see that three people worked on the composer, two people worked on automations. I can stay knowledgeable about what’s happening, because things get chaotic right before launch.

**Thibault Sottiaux**

One automation I have runs multiple times a day. It picks a random file and finds and fixes a subtle bug. It actually does pick a random file—it runs Python random, finds a file, and starts from there. Every time it explores a new one.

**Dan Shipper**

Has it caught anything?

**Thibault Sottiaux**

Oh yeah. It’s often latent bugs that aren’t triggering on the critical path, but they’re actually bugs. Then it’s trivial to fix and merge. It takes very little time. It finds things I would have never found myself. It found an issue in constrained sampling the other day.

**Dan Shipper**

That’s really cool. Do you have other automations worth sharing?

**Andrew Ambrosino**

I feel like I have 60 running at all times. Some for testing, some for real. Some team members really like the one that looks at the PRs you’ve done in the past day and quietly cleans up any bugs you shipped. It checks a few observability platforms and tries to ship a fix before anyone notices you shipped a bug.

**Thibault Sottiaux**

That’s cool. One of mine isn’t coding related—it’s marketing research. It runs daily with a specific skill I’ve tuned over time to do deep marketing research. It searches the web for anything new about how users are perceiving and talking about Codex, then sends me a little report. It always makes for an interesting read. We could go on. These are just examples we rely on. They run.

**Dan Shipper**

Do you have any particular skills you like beyond the normal stuff like the GitHub skill?

**Thibault Sottiaux**

I love Andrew’s YT skill. It takes the change, does the commit, does the PR, writes the draft, puts it in draft, and publishes a PR with a title and body.

**Andrew Ambrosino**

It’s very satisfying.

**Thibault Sottiaux**

It does everything. It definitely makes people productive. What are the top ones for you?

**Andrew Ambrosino**

Image gen is a cool one. For silly automation purposes, like “make me an image that characterizes my previous day of work.”

**Thibault Sottiaux**

Yes, yes.

**Andrew Ambrosino**

The image gen skill was actually really cool for something specific. I used the Codex app to make a book for my daughters. I put together a prompt for a script I wanted written—24 pages, my daughters’ ages, where we’ve lived. We were in Boston, moved to New York, then moved here. After I agreed on the script, I said it’s time to use the image gen skill. It prompted for every page based on the script, generated the images, put them all together using the PDF skill, and I printed it. We’ve got a super custom book that I read to my kids. It’s really cool.

**Thibault Sottiaux**

It’s awesome when you can combine the intelligence of the agent working in a programmatic way using skills and combine them in novel ways. The PDF and image gen combo is common.

**Dan Shipper**

It feels like the Codex model has obviously gotten faster, which makes it much more usable. It also feels a little more emotionally intelligent, but it still has a bit of that “does exactly what you say” thing in a way that can be annoying. How are you thinking about shaping how the model feels and which direction you’re pushing it?

**Thibault Sottiaux**

It’s something we obsess over. We want the model to excel at coding and be really good at instruction following. At the same time, when we optimize too much in that direction, it can overindex on specific words or misunderstand intent in ways humans wouldn’t. Sometimes I have a typo and it ends up in the file. Obviously I didn’t mean the typo—I meant this class name.

That’s something we’re continuing to push on, but the thing we’re pushing on most right now is efficiency and speed. Also what we now call personalities. How supportive is it? We understand not everybody has the same preferences. The previous default was super blunt, pragmatic. Now we’ve introduced a more supportive, friendly personality and you can switch between them. For things that don’t have a universally accepted standard, we’ll probably introduce ways to make it your own. You should feel like you have your own personal Codex that works exactly how you want. Do you use friendly or pragmatic?

**Andrew Ambrosino**

Pragmatic.

**Thibault Sottiaux**

Pragmatic. I also use Pragmatic.

**Dan Shipper**

You guys recently put out a model that is so fast. I was testing it before it came out and I just couldn’t keep up with it. How does that change how you think about what’s now possible with coding, and the affordances you need to manage models that quickly and effectively?

**Andrew Ambrosino**

The first time we used this model in the app, there was just this wall of text and we were at the bottom of the scroll. We immediately said, all right, we need to smooth this out. We actually slow it down ever so slightly so you can see the words come in a little smoother.

**Thibault Sottiaux**

That’s so funny.

**Andrew Ambrosino**

It’s a really funny problem. But this thing has been super fun. What I’m most excited about is what capabilities we can start adding to the app that are really dynamic—things we couldn’t do with a model that wasn’t this fast. Yes, this model lets you iterate really quickly, but it also opens up new opportunities for how you code and interact with the Codex app.

**Thibault Sottiaux**

The first time I showed the very first prototype, when we hooked everything up—the model is powered by Cerebras and we’ve talked about that partnership, we’re very excited to put the first model we’re serving through that out there. It’s still very early, literally the first time we hooked it all up, and we’re just so excited we want to share it.

The first time I showed it to someone, they were like, no way. This is a fake demo. This is not real. This cannot be this fast. Then they tried a few prompts and said, I literally cannot keep up. This is insane.

This will change everything, especially because it’s not yet the fastest we can actually get it to be. With the preview we’re putting it out quite early. We’re going to layer a number of optimizations on top that should make it two to three times faster than what you’ve experienced. That’s going to change things.

We’re also thinking about this from the point of view of delegation. We think this model has a huge role to play as part of multi-agent systems, as a way to speed up the slower, more intelligent agent. We’re going to be experimenting in that direction.

**(00:30:00)**

**Dan Shipper**

Do you expect the same hardware speedups on the more intelligent agents to come out soon?

**Thibault Sottiaux**

A lot of what we worked on were interesting distributed systems and infrastructure problems that we uncovered because we were able to sample from the model at unprecedented speeds. When you’re getting tokens back that fast, you need to optimize the entire set of bottlenecks on the critical path. All of that benefits O3 Codex and all future models.

One thing we’ve been doing that we’ll put in a more detailed blog post at some point: we rewrote the entire server stack to be based on WebSockets with a persistent connection, doing things more incrementally and statefully. That decreases overall latency across all models. We haven’t shipped it by default yet, but it’s the default for this new super fast model. We’re going to enable it on other models too. It decreases overall turn latency by something like 30 to 40 percent.

**Dan Shipper**

What are the most surprising things you’ve seen using the model internally? In terms of what a speedup like this enables.

**Thibault Sottiaux**

It just allows you to be super in the flow. You’re almost in real time sculpting the experience or the code. It’s a very different feeling. It’s unsettling at first, and then once you get into it, it’s very hard to go back to any other model. That’s the feedback we’ve seen, and that’s what I’ve felt myself. It takes about five minutes to adapt, and then you know how you’re going to use this thing.

**Andrew Ambrosino**

I also don’t think we’ve poked at the full extent of what we could do with it. It’s very early. We haven’t had it for very long.

**Thibault Sottiaux**

Someone on the team, Channing, was showing that it’s so fast the model can actually play Pong. Not very well, but it’s able to react to things almost in real time.

**Andrew Ambrosino**

You start to see how it might replace some deterministic steps. We have a set of Git actions in the Codex app. As everybody knows, certain configurations or states in Git can make it really hard to run those without a ton of error handling and error messages and guidance. It’s really hard to create a good Git experience, which is why nobody ever has.

But if you have a model that’s almost as fast as running scripts, you can imagine a world where these things turn into skills. Your operations run differently with some intelligence, without the same latency you have today when asking it to track something down. You can vaguely gesture and say, hey, send this up, and have that be fast enough for a button.

**Thibault Sottiaux**

What I’m very excited about is when it comes together with something we shipped with O3 Codex called mid-turn steering. You start with your prompt, it gets to work, then you send another prompt while it’s still working and it adapts in real time. It receives that message, acknowledges it, and continues its work.

If you start to think about what this looks like with voice and a model as fast as the one we just shipped—that’s a whole other experience we’d be very excited to bring, hopefully very quickly.

**Dan Shipper**

Because you can easily interrupt as you’re talking.

**Thibault Sottiaux**

Yeah. If you’re talking and engaging with natural language, doing mid-turn steers while the implementation happens almost instantly because of the speed, it becomes very pleasant to use. Right now you can emulate it with voice dictation, mid-turn steering, and watching the model implement. It’s a very cool thing. We’re going to have a step change in that experience when we really polish it.

**Dan Shipper**

If speed as a bottleneck is close to being solved, what’s the next bottleneck? What’s the next limit on making the thing you want?

**Thibault Sottiaux**

The bottleneck that’s very apparent is how fast you can verify that things are correct. We can generate code faster than ever before. We can implement entire features. I saw someone, based on a description of the Codex app synthesized into a plan from screenshots, and the models are capable of reproducing 95 percent of the features and rebuilding the app from scratch.

Now, is it going to be bug free? Is everything implemented to perfection the same way the actual app is? That still takes a lot of time for a human to click and verify and make sure the designs are consistent, that there are no bugs, that the settings panel actually does what you expect when you click that button.

Verification definitely becomes a bottleneck. We have people on the team complaining there’s too much code to review. That’s what we’re trying to solve for.

**Andrew Ambrosino**

I complain about that. There’s so much code to review now—both on your own machine and from peers. We’re going to have to figure that out.

**Thibault Sottiaux**

You’re already reviewing the code the first time because the agent presents it to you, and then you have to review code produced by your peers. There are two rounds of review.

**Andrew Ambrosino**

This is something we’re working on. A lot of us still do code review after. We’re looking at what that experience should look like with the model involved. We’ve got a review mode in the Codex app that works nicely—it annotates your diffs on the side with findings and stylistic things. Lots to do.

**Thibault Sottiaux**

One thing I’m excited about with making models faster: you can use it to understand code, understand features, help with code review, help understand what a peer wrote. It’s much more pleasant because this is something you want to be in the flow for. It has to be synchronous. You cannot delegate understanding—you’re trying to get to understanding something, and speed there is a real advantage. It helps offset the fact that models are producing more and more code; speed helps you understand that code faster.

**Dan Shipper**

I’ve found this already with this new model. Speed, especially for end-to-end testing, is faster. When you’re doing manual integration testing, often there’s a toast that pops up for a second, and if the model’s not fast, it’s not going to catch it. The cycle times are much shorter.

I definitely find this too: I can produce so much code, but when I see a PR come in or make one, my first question is, is there evidence you’ve actually tested this? That it actually works—not just unit tests, but you’ve gone through it end to end.

**Thibault Sottiaux**

How do you handle this?

**Andrew Ambrosino**

I’ve seen a lot of peer PRs where I have the same question. It’s so easy to code things now. We have gotten the Codex app pretty good at running itself through some skills—clicking around, screenshotting itself for evidence, uploading it to the PR.

There’s a lot that’s interesting there, especially when we make this more async or when the models get really fast at this stuff. I don’t know exactly what it looks like yet, but there’s a lot around: here’s a bug fix, this is exactly what it looked like when it was happening, here’s exactly what it looks like now with the same click path.

Maybe that’s the turning point—code review becomes less important when you can verify that part instead. You have to do less through the code as a proxy. There’s definitely more to explore there.

**(00:40:00)**

**Dan Shipper**

Last couple questions. What have you guys learned from Cursor and Claude Code, and how do you think about your positioning in the market versus them? What do you think about the differences?

**Thibault Sottiaux**

I think they were first to put something out there, and that was interesting to us because we had been working on similar ideas for a bit. But our models at the time were not ready—they weren’t reliable for long-horizon tasks, they weren’t able to do reliable tool calls and stay on topic.

As soon as we started to really invest in that, especially with GPT-5, we knew the models were there and we knew how to make them even better. O2 brought even better long-context, long-horizon reliability and context understanding. What we were seeing is that Anthropic was losing a little bit of steam when it came to the model.

We were in this fortunate position where the way we run Codex, we’ve got product, engineering, and research all working together, sitting together, solving problems together. It’s a highly creative space. Sometimes we solve problems in the product and the harness, but sometimes we say, hey, how can we actually improve the model? Let’s talk about it and ideate together. Then research will come and say, we’ve got this breakthrough we’re sitting on—would this be something we can ship? And we get excited about that.

One example: we had a lot of complaints about compaction. People felt like whenever they hit compaction, it was losing too much context. So we solved that end to end. We decided to do end-to-end RL training and introduce compaction within research, making the model itself very familiar with the concept and able to produce optimal results—essentially delegating to itself across time.

Once we solved it at the model level, the harness problem became so much easier. Just let the model do it and it’s very reliable. Through that collaboration, the momentum has been very strong. We’re able to improve models and ship on roughly a monthly cadence.

We also took a different bet with the Codex app, which turned out to be awesome. Not forcing ourselves to cram everything into the CLI. It was a great challenge—let’s build an app, where do I get started? And then you just get obsessed with it.

**Andrew Ambrosino**

It’s hard not to.

**Thibault Sottiaux**

How was it to build something that was quite contrarian?

**Andrew Ambrosino**

I remember you and I talking about whether we’d even ship this. Early on we were like, we don’t know if we’ll ship this. We’ll try it out, see if we can get there with something we love. I remember saying, let’s get some PMF internally. Let’s get everybody at OpenAI to want to use this thing without being forced to use it. Let’s see if we can do it.

We did. It was adopted very quickly. The minute it was barely usable, the research folks put dev boxes on it—which was this crazy hack at the time. But now they use it for everything.

**Thibault Sottiaux**

Including training O3 Codex. I feel really good about having hit the point where almost everyone technical at the company uses Codex, but the people who use it the most are actually building Codex and building the models. We’re able to improve things at crazy speeds, and there’s no sign of it slowing down.

**Dan Shipper**

Amazing. I’m excited for what you ship next. Thank you guys for your time. I really appreciate it.

**Thibault Sottiaux**

Thank you. Thanks for having us.

**Andrew Ambrosino**

Thanks.

_Thanks to _**_Scott Nover_**_ for editorial support._

**_Dan Shipper_**_ is the cofounder and CEO of Every, where he writes the [Chain of Thought](https://every.to/chain-of-thought) column and hosts the podcast [AI & I](https://open.spotify.com/show/5qX1nRTaFsfWdmdj5JWO1G). You can follow him on X at [@danshipper](https://twitter.com/danshipper) and on [LinkedIn](https://www.linkedin.com/in/danshipper/)._

_To read more essays like this, subscribe to [Every](https://every.to/subscribe), and follow us on X at [@every](http://twitter.com/every) and on [LinkedIn](https://www.linkedin.com/company/everyinc/)._

_We [build AI tools](https://every.to/studio) for readers like you. Write brilliantly with _**_[Spiral](https://writewithspiral.com/)_**_. Organize files automatically with _**_[Sparkle](https://makeitsparkle.co/?utm_source=everyfooter)_**_. Deliver yourself from email with _**_[Cora](https://cora.computer/)_**_. Dictate effortlessly with _**_[Monologue](https://monologue.to/)_**_._

_We also do AI training, adoption, and innovation for companies. [Work with us](https://every.to/consulting?utm_source=emailfooter) to bring AI into your organization._

_Get paid for sharing Every with your friends. Join our [referral program](https://every.getrewardful.com/signup)._

_For sponsorship opportunities, reach out to sponsorships@every.to._

_Help us scale the only subscription you need to stay at the edge of AI. Explore [open roles at Every](https://www.notion.so/Jobs-Every-25cca4f355ac80c5ad6ee7a6e93d6b4e?pvs=21)._

[Subscribe](https://every.to/subscribe?source=post_button)
