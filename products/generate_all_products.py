from fpdf import FPDF
import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

class ProductPDF(FPDF):
    def __init__(self, title, color, subtitle="", author="GetTradeRadar.com"):
        super().__init__()
        self.title_text = title
        self.color = color  # tuple (r, g, b)
        self.subtitle = subtitle
        self.author_text = author
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_fill_color(*self.color)
            self.rect(0, 0, 210, 8, 'F')
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(100, 100, 100)
            self.set_y(10)
            self.cell(0, 5, self.title_text, align='C')
            self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()} | {self.author_text}', align='C')

    def cover_page(self):
        self.add_page()
        self.set_fill_color(*self.color)
        self.rect(0, 0, 210, 297, 'F')
        self.set_fill_color(15, 23, 42)  # dark overlay
        self.rect(20, 40, 170, 180, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 28)
        self.set_y(70)
        self.cell(0, 15, self.title_text, align='C')
        if self.subtitle:
            self.ln(20)
            self.set_font('Helvetica', '', 14)
            self.cell(0, 10, self.subtitle, align='C')
        self.set_y(160)
        self.set_font('Helvetica', 'I', 12)
        self.cell(0, 10, f'By {self.author_text}', align='C')
        self.ln(10)
        self.cell(0, 10, 'gettraderadar.com', align='C')

    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(*self.color)
        self.cell(0, 10, title)
        self.ln(5)
        self.set_draw_color(*self.color)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(8)
        self.set_text_color(50, 50, 50)

    def body_text(self, text):
        self.set_font('Helvetica', '', 11)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 6, text)
        self.ln(3)

    def bullet(self, text):
        self.set_font('Helvetica', '', 11)
        x = self.get_x()
        self.cell(8, 6, '-')
        self.multi_cell(0, 6, text)
        self.ln(1)

    def bold_text(self, text):
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def back_page(self):
        self.add_page()
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 297, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 20)
        self.set_y(80)
        self.cell(0, 15, 'Want More?', align='C')
        self.ln(15)
        self.set_font('Helvetica', '', 13)
        self.cell(0, 10, 'Visit gettraderadar.com for:', align='C')
        self.ln(15)
        self.set_font('Helvetica', '', 12)
        for item in ['AI Trading Signals ($47/mo)', 'Premium Courses & Guides', 'Free Resources & Tools', 'Community Access']:
            self.cell(0, 8, f'> {item}', align='C')
            self.ln(8)
        self.ln(15)
        self.set_text_color(*self.color)
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'gettraderadar.com', align='C')


def gen_ai_money():
    pdf = ProductPDF("100 AI Side Hustle Prompts", (16, 185, 129), "Your Complete AI Prompt Collection")
    pdf.cover_page()

    categories = {
        "Content Writing": [
            ("Blog Post Generator", "Write a 1500-word blog post about [topic] targeting [audience]. Include an engaging hook, 5 subheadings with actionable tips, and a compelling CTA."),
            ("Email Sequence", "Create a 5-email welcome sequence for [business type] that builds trust and converts subscribers into customers."),
            ("Product Description", "Write 3 versions of a product description for [product] highlighting benefits over features, targeting [demographic]."),
        ],
        "Social Media": [
            ("Viral Hook Generator", "Generate 10 scroll-stopping hooks for [platform] about [topic] that create curiosity gaps."),
            ("Content Calendar", "Create a 30-day social media content calendar for [niche] with post ideas, hashtags, and best posting times."),
            ("Story Script", "Write a 60-second Instagram/TikTok story script that uses the PAS framework to promote [product/service]."),
        ],
        "Business Planning": [
            ("Business Model Canvas", "Create a complete Business Model Canvas for a [type] business targeting [market], including revenue streams and cost structure."),
            ("Competitor Analysis", "Analyze [competitor] and identify 5 gaps in their offering that a new entrant could exploit."),
            ("Financial Projection", "Create a 12-month financial projection for a [business type] starting with $[budget] investment."),
        ],
        "SEO & Marketing": [
            ("Keyword Cluster", "Generate a keyword cluster of 30 terms around [main keyword] organized by search intent."),
            ("Landing Page Copy", "Write high-converting landing page copy for [product] using the AIDA framework with social proof elements."),
            ("Ad Copy Pack", "Create 5 Facebook ad variations for [product] with different angles: pain point, aspiration, social proof, urgency, curiosity."),
        ],
    }

    for cat, prompts in categories.items():
        pdf.add_page()
        pdf.chapter_title(cat)
        for i, (title, prompt) in enumerate(prompts, 1):
            pdf.bold_text(f"{i}. {title}")
            pdf.body_text(f"Prompt: {prompt}")
            pdf.body_text("Pro Tip: Customize the bracketed sections for your specific use case. The more specific you are, the better the output.")
            pdf.ln(3)

    pdf.back_page()
    pdf.output(os.path.join(OUTPUT_DIR, "100_ai_side_hustle_prompts.pdf"))
    print("Created: 100_ai_side_hustle_prompts.pdf")


def gen_tech_guide():
    pdf = ProductPDF("Tech Career Pivot Guide", (59, 130, 246), "Your Roadmap to a Tech Career")
    pdf.cover_page()

    pdf.add_page()
    pdf.chapter_title("Chapter 1: Why Tech, Why Now")
    pdf.body_text("The tech industry continues to grow despite economic uncertainty. Remote work opportunities, high salaries, and constant innovation make tech one of the best career moves you can make.")
    pdf.bold_text("Key Stats:")
    pdf.bullet("3.5 million unfilled cybersecurity jobs globally by 2025")
    pdf.bullet("Average tech salary: $95,000-$150,000 depending on role")
    pdf.bullet("85% of tech jobs allow remote or hybrid work")
    pdf.bullet("Tech industry growing 2x faster than overall economy")

    roles = [
        ("Software Developer", "$70K-$150K", "Python, JavaScript, React, Git"),
        ("Data Analyst", "$55K-$95K", "SQL, Python, Tableau, Excel"),
        ("UX Designer", "$65K-$120K", "Figma, User Research, Prototyping"),
        ("Cloud Engineer", "$80K-$160K", "AWS, Azure, Docker, Kubernetes"),
        ("Cybersecurity Analyst", "$70K-$130K", "Networks, SIEM, Compliance"),
        ("Product Manager", "$90K-$170K", "Strategy, Agile, Communication"),
        ("DevOps Engineer", "$85K-$155K", "CI/CD, Linux, Terraform, Monitoring"),
        ("AI/ML Engineer", "$100K-$200K", "Python, TensorFlow, PyTorch, Math"),
    ]

    pdf.add_page()
    pdf.chapter_title("Chapter 2: Top 8 Tech Roles")
    for role, salary, skills in roles:
        pdf.bold_text(f"{role} - {salary}")
        pdf.body_text(f"Key Skills: {skills}")
        pdf.ln(2)

    pdf.add_page()
    pdf.chapter_title("Chapter 3: Free Learning Resources")
    pdf.bullet("freeCodeCamp.org - Full-stack web development (free)")
    pdf.bullet("CS50 by Harvard (edX) - Best intro to computer science (free)")
    pdf.bullet("Google IT Support Certificate (Coursera) - Entry-level IT")
    pdf.bullet("The Odin Project - Web development bootcamp (free)")
    pdf.bullet("Kaggle Learn - Data science and ML courses (free)")
    pdf.bullet("TryHackMe - Cybersecurity hands-on learning")
    pdf.bullet("AWS Free Tier + Cloud Practitioner prep")

    pdf.add_page()
    pdf.chapter_title("Chapter 4: 90-Day Action Plan")
    pdf.bold_text("Days 1-30: Foundation")
    pdf.bullet("Pick ONE role from Chapter 2 that excites you")
    pdf.bullet("Start 1 free course from Chapter 3")
    pdf.bullet("Dedicate 1-2 hours daily to learning")
    pdf.bullet("Join 2-3 tech communities on Discord/Reddit")
    pdf.bold_text("Days 31-60: Build")
    pdf.bullet("Complete your first course or certification")
    pdf.bullet("Build 2-3 portfolio projects")
    pdf.bullet("Start a GitHub profile and push code daily")
    pdf.bullet("Write about your learning journey on LinkedIn")
    pdf.bold_text("Days 61-90: Launch")
    pdf.bullet("Update resume with new skills and projects")
    pdf.bullet("Apply to 5-10 positions per week")
    pdf.bullet("Practice mock interviews on Pramp or Interviewing.io")
    pdf.bullet("Network at virtual meetups and conferences")

    pdf.back_page()
    pdf.output(os.path.join(OUTPUT_DIR, "tech_career_pivot_guide.pdf"))
    print("Created: tech_career_pivot_guide.pdf")


def gen_motivation_journal():
    pdf = ProductPDF("90-Day Transformation Journal", (249, 115, 22), "Your Daily Guide to Growth")
    pdf.cover_page()

    pdf.add_page()
    pdf.chapter_title("How to Use This Journal")
    pdf.body_text("This journal is your daily companion for transformation. Each day, spend 5-10 minutes in the morning and 5 minutes in the evening completing the prompts. Consistency is the key - even on hard days, write SOMETHING.")
    pdf.bold_text("Morning Routine (5-10 min):")
    pdf.bullet("Set your daily intention - what do you want to achieve?")
    pdf.bullet("Write 3 things you're grateful for")
    pdf.bullet("Define your #1 goal for the day")
    pdf.bold_text("Evening Reflection (5 min):")
    pdf.bullet("Rate your day 1-10")
    pdf.bullet("What went well? What could improve?")
    pdf.bullet("What are you proud of?")

    for week in range(1, 5):  # 4 weeks shown, template for rest
        pdf.add_page()
        pdf.chapter_title(f"Week {week}")
        for day in range(1, 8):
            day_num = (week-1)*7 + day
            if day_num > 90: break
            pdf.bold_text(f"Day {day_num}")
            pdf.body_text(f"Date: ___/___/___")
            pdf.body_text("Morning Intention: ________________________________")
            pdf.body_text("Grateful for: 1)_______ 2)_______ 3)_______")
            pdf.body_text("Today's #1 Goal: ________________________________")
            pdf.body_text("Evening Rating: ___/10 | Proud of: _______________")
            pdf.ln(3)

    pdf.add_page()
    pdf.chapter_title("Weekly Review Template")
    pdf.body_text("Complete this every Sunday:")
    pdf.bullet("Biggest win this week: ______________________")
    pdf.bullet("Biggest lesson learned: ______________________")
    pdf.bullet("What will I do differently next week? __________")
    pdf.bullet("Am I closer to my 90-day goal? Why/why not?")
    pdf.bullet("Self-care check: Sleep___  Exercise___  Nutrition___")

    pdf.back_page()
    pdf.output(os.path.join(OUTPUT_DIR, "90_day_transformation_journal.pdf"))
    print("Created: 90_day_transformation_journal.pdf")


def gen_health_guide():
    pdf = ProductPDF("Herbal Remedies Quick Guide", (5, 150, 105), "Natural Solutions for Everyday Health")
    pdf.cover_page()

    herbs = [
        ("Turmeric", "Anti-inflammatory, joint health, brain function", "Add to food, golden milk, or take 500mg capsule with black pepper", "May interact with blood thinners"),
        ("Ashwagandha", "Stress reduction, energy, sleep quality", "300-600mg standardized extract daily", "Avoid during pregnancy, may affect thyroid meds"),
        ("Ginger", "Digestion, nausea, inflammation", "Fresh in tea, 250mg capsule, or add to meals", "May increase bleeding risk at high doses"),
        ("Chamomile", "Sleep, anxiety, digestive comfort", "1-2 cups tea before bed, or 400mg capsule", "Avoid if allergic to ragweed family"),
        ("Echinacea", "Immune support, cold prevention", "Take at first sign of illness for 7-10 days", "Not for autoimmune conditions"),
        ("Peppermint", "Digestion, headaches, focus", "Tea, essential oil (diluted), or enteric capsules", "May worsen acid reflux in some people"),
        ("Lavender", "Anxiety, sleep, pain relief", "Essential oil, tea, or 80mg capsule daily", "Generally very safe, avoid ingesting essential oil"),
        ("Valerian Root", "Sleep, anxiety, muscle relaxation", "300-600mg 30 min before bed", "May cause drowsiness, don't mix with sedatives"),
        ("Ginseng", "Energy, cognitive function, immunity", "200-400mg standardized extract daily", "May affect blood sugar and blood pressure"),
        ("Elderberry", "Immune support, cold and flu relief", "Syrup or capsule during illness season", "Only use commercially prepared products"),
    ]

    pdf.add_page()
    pdf.chapter_title("Safety First")
    pdf.body_text("Always consult a healthcare provider before starting any herbal supplement, especially if you take medications or have health conditions. Herbs are powerful and can interact with drugs.")

    for name, benefits, usage, warnings in herbs:
        pdf.add_page()
        pdf.chapter_title(name)
        pdf.bold_text("Benefits:")
        pdf.body_text(benefits)
        pdf.bold_text("How to Use:")
        pdf.body_text(usage)
        pdf.bold_text("Warnings:")
        pdf.body_text(warnings)

    pdf.back_page()
    pdf.output(os.path.join(OUTPUT_DIR, "herbal_remedies_guide.pdf"))
    print("Created: herbal_remedies_guide.pdf")


def gen_meditation():
    pdf = ProductPDF("Mindfulness Meditation Pack", (139, 92, 246), "10 Guided Meditation Scripts")
    pdf.cover_page()

    meditations = [
        ("Morning Calm", "5 min", "Start your day centered", "Find a comfortable seated position. Close your eyes. Take 3 deep breaths - in through the nose for 4 counts, hold for 4, out through the mouth for 6. Feel the stillness of the morning. Set an intention for your day. With each breath, feel energy and calm filling your body. Visualize your day going exactly as you want it. When ready, open your eyes and carry this calm with you."),
        ("Body Scan", "10 min", "Release physical tension", "Lie down comfortably. Starting at the top of your head, slowly scan down through your body. Notice any tension in your forehead... jaw... neck... shoulders. Breathe into each area of tension. Let it soften and release. Continue down through your arms, chest, belly, hips, legs, all the way to your toes. Feel your entire body supported and relaxed."),
        ("Stress Release", "7 min", "Let go of anxiety", "Sit quietly and imagine stress as a color - perhaps red or gray. See it in your body where you feel tension. Now imagine a cooling blue light entering from above, slowly washing through you, dissolving the stress color. With each exhale, the stress leaves your body. With each inhale, peace fills the space. You are safe. You are calm. You are in control."),
        ("Sleep Preparation", "10 min", "Fall asleep naturally", "Lying in bed, let your body sink into the mattress. Imagine you are floating on a calm, warm lake under the stars. The water supports you completely. Count backwards from 50, and with each number, you sink a little deeper into relaxation. If your mind wanders, gently return to counting. There is nowhere to be. Nothing to do. Just rest."),
        ("Gratitude", "5 min", "Cultivate appreciation", "Close your eyes and bring to mind 3 things you are grateful for today. They can be simple - a warm cup of coffee, a kind word, sunshine. For each one, really FEEL the gratitude in your chest. Let it expand and warm you. Gratitude is the fastest path to happiness. Carry this feeling with you today."),
    ]

    for title, duration, purpose, script in meditations:
        pdf.add_page()
        pdf.chapter_title(f"{title} ({duration})")
        pdf.bold_text(f"Purpose: {purpose}")
        pdf.ln(3)
        pdf.body_text(script)

    pdf.add_page()
    pdf.chapter_title("30-Day Meditation Challenge")
    pdf.body_text("Week 1: Morning Calm daily (build the habit)")
    pdf.body_text("Week 2: Alternate Morning Calm + Body Scan")
    pdf.body_text("Week 3: Add Gratitude meditation to evenings")
    pdf.body_text("Week 4: Choose your favorite + try Sleep Preparation")
    pdf.bold_text("Rules: Never miss twice in a row. Even 2 minutes counts. Track with a simple checkmark calendar.")

    pdf.back_page()
    pdf.output(os.path.join(OUTPUT_DIR, "mindfulness_meditation_pack.pdf"))
    print("Created: mindfulness_meditation_pack.pdf")


def gen_limitless():
    pdf = ProductPDF("Limitless Mind Mastery", (6, 182, 212), "Unlock Your Full Potential", "GetTradeRadar.com")
    pdf.cover_page()

    pdf.add_page()
    pdf.chapter_title("Module 1: Growth Mindset Foundation")
    pdf.body_text("Your beliefs about your abilities determine everything. A fixed mindset says 'I'm not smart enough.' A growth mindset says 'I haven't learned this YET.'")
    pdf.bold_text("Exercise: Reframe 5 limiting beliefs")
    pdf.bullet("'I'm bad at math' -> 'I'm developing my math skills'")
    pdf.bullet("'I'm not a leader' -> 'I'm building leadership qualities'")
    pdf.bullet("Write your own: ________________________________")

    pdf.add_page()
    pdf.chapter_title("Module 2: Goal Setting (SMART+)")
    pdf.body_text("SMART+ goals add Emotional connection and Accountability to the traditional framework.")
    pdf.bullet("Specific: What exactly do you want?")
    pdf.bullet("Measurable: How will you track progress?")
    pdf.bullet("Achievable: Is it realistic with effort?")
    pdf.bullet("Relevant: Does it align with your values?")
    pdf.bullet("Time-bound: When is your deadline?")
    pdf.bullet("+ Emotional: WHY does this matter to you?")
    pdf.bullet("+ Accountable: Who will hold you to it?")

    pdf.add_page()
    pdf.chapter_title("Module 3: Habit Stacking")
    pdf.body_text("Attach new habits to existing ones. Formula: After I [CURRENT HABIT], I will [NEW HABIT].")
    pdf.bullet("After I pour my morning coffee, I will write my 3 goals")
    pdf.bullet("After I sit at my desk, I will do 2 min of deep breathing")
    pdf.bullet("After I eat lunch, I will take a 10-min walk")
    pdf.bold_text("Your habit stack (fill in):")
    pdf.body_text("After I ____________, I will ____________")
    pdf.body_text("After I ____________, I will ____________")
    pdf.body_text("After I ____________, I will ____________")

    pdf.add_page()
    pdf.chapter_title("Module 4: Productivity Mastery")
    pdf.bold_text("The 3-3-3 Method:")
    pdf.bullet("3 hours of deep work on your #1 priority")
    pdf.bullet("3 shorter tasks (emails, calls, admin)")
    pdf.bullet("3 maintenance activities (health, relationships, learning)")
    pdf.body_text("This framework ensures you make progress on what matters while handling daily responsibilities.")

    pdf.add_page()
    pdf.chapter_title("Module 5: Emotional Intelligence")
    pdf.body_text("EQ is the #1 predictor of success. The four pillars:")
    pdf.bullet("Self-Awareness: Know your emotions in real-time")
    pdf.bullet("Self-Management: Control reactions, stay composed")
    pdf.bullet("Social Awareness: Read others' emotions accurately")
    pdf.bullet("Relationship Management: Inspire and influence positively")
    pdf.bold_text("Daily EQ Exercise:")
    pdf.body_text("Three times today, pause and ask: 'What am I feeling right now? Why? Is this serving me?'")

    pdf.add_page()
    pdf.chapter_title("Your 12-Month Transformation Plan")
    pdf.bold_text("Months 1-3: Foundation")
    pdf.body_text("Focus on mindset, habits, and morning routine. Read 3 books. Build 1 new skill.")
    pdf.bold_text("Months 4-6: Acceleration")
    pdf.body_text("Launch a side project. Expand your network. Take on a leadership challenge.")
    pdf.bold_text("Months 7-9: Mastery")
    pdf.body_text("Deepen your expertise. Mentor someone. Create content about your journey.")
    pdf.bold_text("Months 10-12: Legacy")
    pdf.body_text("Build systems that work without you. Set next-level goals. Celebrate your transformation.")

    pdf.back_page()
    pdf.output(os.path.join(OUTPUT_DIR, "limitless_mind_mastery.pdf"))
    print("Created: limitless_mind_mastery.pdf")


def gen_productivity():
    pdf = ProductPDF("Daily Productivity System", (20, 184, 166), "Master Your Time, Master Your Life")
    pdf.cover_page()

    pdf.add_page()
    pdf.chapter_title("The Morning Power Hour")
    pdf.body_text("The first hour of your day determines the rest. No phone for 30 minutes after waking.")
    pdf.bullet("5:30 - Wake up, hydrate (500ml water)")
    pdf.bullet("5:35 - 10 min movement (stretch, walk, or exercise)")
    pdf.bullet("5:45 - 10 min journaling (goals + gratitude)")
    pdf.bullet("5:55 - 5 min meditation or deep breathing")
    pdf.bullet("6:00 - Review your time-blocked schedule")
    pdf.bullet("6:15 - Start your #1 deep work task")

    pdf.add_page()
    pdf.chapter_title("Time Blocking Method")
    pdf.body_text("Schedule EVERYTHING. Unscheduled time gets wasted. Block your day into 3 categories:")
    pdf.bold_text("1. Deep Work Blocks (2-4 hours)")
    pdf.body_text("Your most important, cognitively demanding work. No interruptions. Phone on airplane mode.")
    pdf.bold_text("2. Shallow Work Blocks (1-2 hours)")
    pdf.body_text("Email, calls, admin, meetings. Batch these together.")
    pdf.bold_text("3. Recovery Blocks (30-60 min)")
    pdf.body_text("Breaks, walks, meals, exercise. Non-negotiable for sustained performance.")

    pdf.add_page()
    pdf.chapter_title("The Eisenhower Matrix")
    pdf.body_text("Sort all tasks into 4 quadrants:")
    pdf.bold_text("Q1 - Urgent + Important: DO NOW")
    pdf.body_text("Crises, deadlines, emergencies. Minimize time here through planning.")
    pdf.bold_text("Q2 - Not Urgent + Important: SCHEDULE")
    pdf.body_text("Strategy, learning, relationships, health. This is where success lives.")
    pdf.bold_text("Q3 - Urgent + Not Important: DELEGATE")
    pdf.body_text("Most emails, some meetings, interruptions. Automate or delegate.")
    pdf.bold_text("Q4 - Not Urgent + Not Important: ELIMINATE")
    pdf.body_text("Social media scrolling, busywork, time-wasters. Cut ruthlessly.")

    pdf.add_page()
    pdf.chapter_title("Focus Techniques")
    pdf.bold_text("The Pomodoro+ Method:")
    pdf.bullet("Work for 25 minutes with total focus")
    pdf.bullet("5 minute break (walk, stretch, breathe)")
    pdf.bullet("After 4 rounds, take a 20-minute break")
    pdf.bullet("The '+': Track what distracted you during each round")
    pdf.bold_text("The 2-Minute Rule:")
    pdf.body_text("If a task takes less than 2 minutes, do it immediately. Don't add it to a list.")

    pdf.add_page()
    pdf.chapter_title("Evening Wind-Down")
    pdf.bullet("Review tomorrow's schedule (5 min)")
    pdf.bullet("Write down your #1 priority for tomorrow")
    pdf.bullet("Clear your desk and close all tabs")
    pdf.bullet("No screens 30 min before bed")
    pdf.bullet("Read, journal, or light stretching")
    pdf.bullet("Consistent sleep time (non-negotiable)")

    pdf.back_page()
    pdf.output(os.path.join(OUTPUT_DIR, "daily_productivity_system.pdf"))
    print("Created: daily_productivity_system.pdf")


def gen_dropshipping():
    pdf = ProductPDF("Dropshipping Blueprint", (244, 63, 94), "Build Your E-Commerce Empire")
    pdf.cover_page()

    pdf.add_page()
    pdf.chapter_title("Chapter 1: Niche Selection")
    pdf.body_text("The right niche makes or breaks your store. Look for:")
    pdf.bullet("Products priced $15-70 (sweet spot for impulse buys)")
    pdf.bullet("Lightweight items (cheap shipping)")
    pdf.bullet("Problem-solving products (easier to market)")
    pdf.bullet("Avoid electronics (high return rate) and branded items")
    pdf.bold_text("Top 5 Niches Right Now:")
    pdf.bullet("Pet accessories (endless demand, emotional buying)")
    pdf.bullet("Home organization (practical, visual for ads)")
    pdf.bullet("Fitness accessories (recurring buyers)")
    pdf.bullet("Phone/tech accessories (high margin)")
    pdf.bullet("Kitchen gadgets (viral potential)")

    pdf.add_page()
    pdf.chapter_title("Chapter 2: Finding Suppliers")
    pdf.bold_text("Top Platforms:")
    pdf.bullet("AliExpress - Largest selection, 2-4 week shipping")
    pdf.bullet("CJ Dropshipping - Faster shipping, US warehouses")
    pdf.bullet("Spocket - US/EU suppliers, 2-5 day shipping")
    pdf.bullet("Zendrop - Auto-fulfillment, branded packaging")
    pdf.bold_text("Supplier Red Flags:")
    pdf.bullet("Less than 4.5 star rating")
    pdf.bullet("Less than 95% positive feedback")
    pdf.bullet("No response within 24 hours")
    pdf.bullet("Inconsistent product photos")

    pdf.add_page()
    pdf.chapter_title("Chapter 3: Store Setup (Shopify)")
    pdf.bullet("Sign up for Shopify ($1/month for first 3 months)")
    pdf.bullet("Choose a clean, fast theme (Dawn is free and great)")
    pdf.bullet("Add 10-20 products to start")
    pdf.bullet("Write compelling product descriptions (benefits > features)")
    pdf.bullet("Set up payment processing (Shopify Payments)")
    pdf.bullet("Create essential pages: About, Contact, Shipping, Returns")
    pdf.bullet("Install apps: DSers (AliExpress), Vitals (reviews + upsells)")

    pdf.add_page()
    pdf.chapter_title("Chapter 4: Facebook Ads Basics")
    pdf.bold_text("Your First Campaign:")
    pdf.bullet("Budget: $10-20/day testing budget")
    pdf.bullet("Audience: Broad targeting (let Facebook optimize)")
    pdf.bullet("Creative: Video ads outperform images 3x")
    pdf.bullet("Copy: Hook + Problem + Solution + CTA")
    pdf.bold_text("Scaling Rules:")
    pdf.bullet("Kill ads with no sales after $20 spent")
    pdf.bullet("Scale winners by 20% per day (not more)")
    pdf.bullet("Duplicate winning ad sets, don't edit them")
    pdf.bullet("Target ROAS of 2.5x or higher to be profitable")

    pdf.add_page()
    pdf.chapter_title("Chapter 5: Scaling to $10K/Month")
    pdf.bullet("Find 2-3 winning products (test 20+ to find them)")
    pdf.bullet("Scale ad spend on winners to $100-300/day")
    pdf.bullet("Add email marketing (recover 15-20% abandoned carts)")
    pdf.bullet("Introduce upsells and bundles (increase AOV by 30%)")
    pdf.bullet("Test new traffic sources: TikTok Ads, Google Shopping")
    pdf.bullet("Automate everything: fulfillment, emails, customer service")
    pdf.bold_text("Timeline: Most successful stores hit $10K/month within 3-6 months of consistent testing and optimization.")

    pdf.back_page()
    pdf.output(os.path.join(OUTPUT_DIR, "dropshipping_blueprint.pdf"))
    print("Created: dropshipping_blueprint.pdf")


# Generate all products
if __name__ == "__main__":
    print("Generating all digital products...")
    gen_ai_money()
    gen_tech_guide()
    gen_motivation_journal()
    gen_health_guide()
    gen_meditation()
    gen_limitless()
    gen_productivity()
    gen_dropshipping()

    # List all generated PDFs
    print("\n=== All Products Generated ===")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith('.pdf'):
            size = os.path.getsize(os.path.join(OUTPUT_DIR, f))
            print(f"  {f}: {size:,} bytes")
    print(f"\nTotal: {len([f for f in os.listdir(OUTPUT_DIR) if f.endswith('.pdf')])} PDFs")
