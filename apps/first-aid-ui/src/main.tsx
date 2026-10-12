import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import {
  ArrowRight,
  Bot,
  ChevronLeft,
  ChevronRight,
  Clock3,
  HeartPulse,
  Info,
  Lightbulb,
  MessageCircleQuestion,
  Search,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  TimerReset,
} from 'lucide-react'
import './styles.css'

type Tip = {
  title: string
  body: string
  category: 'First aid' | 'Wellbeing' | 'Prevention'
  accent: string
}

const tips: Tip[] = [
  { title: 'Check the scene first', body: 'Before helping, look for traffic, fire, electricity, or other hazards. Keep yourself safe so you can help safely.', category: 'First aid', accent: 'coral' },
  { title: 'Call for help early', body: 'For a serious injury, ask someone to call campus security or emergency services while you stay with the person.', category: 'First aid', accent: 'blue' },
  { title: 'Severe bleeding', body: 'Apply firm, direct pressure with clean cloth or gauze. Keep pressure on and add more layers if blood soaks through.', category: 'First aid', accent: 'coral' },
  { title: 'Minor cuts', body: 'Wash your hands, rinse the wound with clean running water, then cover it with a clean dressing.', category: 'First aid', accent: 'sage' },
  { title: 'Nosebleed position', body: 'Sit upright, lean slightly forward, and pinch the soft part of the nose for 10 to 15 minutes.', category: 'First aid', accent: 'coral' },
  { title: 'Sprains and strains', body: 'Rest the area and use a wrapped cold pack for short periods. Seek help if pain or swelling is severe.', category: 'First aid', accent: 'blue' },
  { title: 'Possible fracture', body: 'Keep the area still in the position found. Do not try to straighten it; get urgent medical help.', category: 'First aid', accent: 'coral' },
  { title: 'Burns', body: 'Cool a minor burn under clean, cool running water for 20 minutes. Do not use ice, butter, or creams.', category: 'First aid', accent: 'coral' },
  { title: 'Chemical exposure', body: 'Move away from the source and rinse exposed skin or eyes with water. Call emergency services or poison control.', category: 'First aid', accent: 'blue' },
  { title: 'Heat exhaustion', body: 'Move to a cool place, loosen clothing, and sip water if alert. Get help if symptoms worsen or do not improve.', category: 'First aid', accent: 'sage' },
  { title: 'Heat stroke warning', body: 'Confusion, fainting, or hot skin is an emergency. Call emergency services and cool the person while waiting.', category: 'First aid', accent: 'coral' },
  { title: 'Cold exposure', body: 'Move indoors, remove wet clothing, and warm gradually with dry layers. Avoid very hot water or direct heat.', category: 'First aid', accent: 'blue' },
  { title: 'Fainting response', body: 'Lay the person flat, check breathing, and raise their legs if there is no injury. Call for help if they do not wake quickly.', category: 'First aid', accent: 'blue' },
  { title: 'Seizure support', body: 'Clear nearby hazards, cushion the head, and time the seizure. Never hold the person down or put anything in their mouth.', category: 'First aid', accent: 'coral' },
  { title: 'Choking: conscious adult', body: 'Encourage coughing if they can breathe. If they cannot, call for help and give appropriate back blows and abdominal thrusts.', category: 'First aid', accent: 'coral' },
  { title: 'Unresponsive person', body: 'Check for a response and normal breathing. Call emergency services and begin CPR if trained and needed.', category: 'First aid', accent: 'coral' },
  { title: 'Use an AED', body: 'Turn on the AED and follow its spoken prompts. It will only deliver a shock when appropriate.', category: 'First aid', accent: 'sage' },
  { title: 'Asthma support', body: 'Help the person sit upright and use their prescribed reliever inhaler. Get urgent help if breathing stays difficult.', category: 'First aid', accent: 'blue' },
  { title: 'Allergic reaction', body: 'Call emergency services for breathing trouble or swelling. Help use an epinephrine auto-injector if prescribed.', category: 'First aid', accent: 'coral' },
  { title: 'Suspected poisoning', body: 'Do not induce vomiting. Keep the product container nearby and contact poison control or emergency services.', category: 'First aid', accent: 'coral' },
  { title: 'Head injury', body: 'Rest and monitor after a minor bump. Repeated vomiting, worsening headache, confusion, or loss of consciousness needs urgent care.', category: 'First aid', accent: 'coral' },
  { title: 'Eye injury', body: 'Do not rub the eye. Rinse with clean water for a chemical splash and seek urgent care for embedded objects or vision changes.', category: 'First aid', accent: 'blue' },
  { title: 'Blister care', body: 'Keep a blister clean and covered. Avoid popping it unless a health professional advises otherwise.', category: 'First aid', accent: 'sage' },
  { title: 'Sunburn relief', body: 'Cool the skin, drink water, and use a moisturizer. Seek care for extensive blistering or signs of heat illness.', category: 'First aid', accent: 'coral' },
  { title: 'When to call emergency services', body: 'Call for chest pain, severe breathing trouble, uncontrolled bleeding, stroke signs, or loss of consciousness.', category: 'First aid', accent: 'coral' },
  { title: 'Wash your hands', body: 'Use soap and running water for at least 20 seconds, especially before eating and after using shared equipment.', category: 'Prevention', accent: 'sage' },
  { title: 'Carry a water bottle', body: 'Keep water nearby during long classes, exams, and exercise. Thirst can arrive after dehydration has started.', category: 'Prevention', accent: 'blue' },
  { title: 'Protect your sleep', body: 'A regular sleep window supports memory, mood, and immune function. Keep late-night study sessions occasional.', category: 'Wellbeing', accent: 'blue' },
  { title: 'Take screen breaks', body: 'Every 20 minutes, look about 20 feet away for 20 seconds to reduce eye strain during study sessions.', category: 'Wellbeing', accent: 'sage' },
  { title: 'Eat before a long day', body: 'A simple meal with protein, fiber, and carbohydrates can support steady energy through classes.', category: 'Wellbeing', accent: 'coral' },
  { title: 'Move between lectures', body: 'A few minutes of walking or stretching can ease stiffness and refresh attention.', category: 'Wellbeing', accent: 'sage' },
  { title: 'Use sunscreen', body: 'Apply broad-spectrum SPF 30 or higher and reapply when outdoors for extended periods.', category: 'Prevention', accent: 'coral' },
  { title: 'Cough etiquette', body: 'Cough into your elbow or a tissue, then wash your hands. Avoid sharing drinks when you feel unwell.', category: 'Prevention', accent: 'blue' },
  { title: 'Stay home when sick', body: 'Rest and reduce close contact when you have a fever or contagious symptoms. Use campus health guidance.', category: 'Prevention', accent: 'blue' },
  { title: 'Keep medicines labeled', body: 'Store medicines in their original containers and never share prescriptions with friends.', category: 'Prevention', accent: 'sage' },
  { title: 'Know your allergies', body: 'Keep a current list of allergies and medications in your phone or wallet for emergencies.', category: 'Prevention', accent: 'coral' },
  { title: 'Read medication labels', body: 'Check active ingredients and directions before taking over-the-counter medicines, especially combination products.', category: 'Prevention', accent: 'blue' },
  { title: 'Do not mix substances', body: 'Alcohol and some medicines can interact dangerously. Ask a pharmacist before combining products.', category: 'Prevention', accent: 'coral' },
  { title: 'Use a helmet', body: 'Wear a properly fitted helmet for biking, skating, and other wheeled activities on and around campus.', category: 'Prevention', accent: 'sage' },
  { title: 'Choose a safe route', body: 'Use lit paths, travel with others at night, and save campus safety contacts in your phone.', category: 'Prevention', accent: 'blue' },
  { title: 'Lift with support', body: 'Ask for help with heavy items, keep the load close, and avoid twisting while lifting.', category: 'Prevention', accent: 'sage' },
  { title: 'Warm up gradually', body: 'Start activity slowly and finish with an easy cool-down to reduce strain and dizziness.', category: 'Prevention', accent: 'coral' },
  { title: 'Know your campus clinic', body: 'Save the clinic hours, location, and after-hours advice before you need them.', category: 'Prevention', accent: 'blue' },
  { title: 'Mental health counts', body: 'Feeling overwhelmed for weeks is a reason to reach out to counseling or a trusted person.', category: 'Wellbeing', accent: 'sage' },
  { title: 'Grounding for stress', body: 'Try naming five things you see, four you feel, three you hear, two you smell, and one you taste.', category: 'Wellbeing', accent: 'coral' },
  { title: 'Pause before exams', body: 'A short breathing break can settle your nervous system: inhale gently, then make the exhale longer.', category: 'Wellbeing', accent: 'blue' },
  { title: 'Support a friend', body: 'Listen without judgment, ask how you can help, and connect them with professional support when needed.', category: 'Wellbeing', accent: 'sage' },
  { title: 'Respect boundaries', body: 'Consent should be clear, freely given, and ongoing. Anyone can change their mind at any time.', category: 'Prevention', accent: 'coral' },
  { title: 'Protect your hearing', body: 'Turn down headphones and take listening breaks, especially in loud venues and rehearsal spaces.', category: 'Prevention', accent: 'blue' },
  { title: 'Keep snacks accessible', body: 'A shelf-stable snack can help if a long class, commute, or medication schedule delays a meal.', category: 'Wellbeing', accent: 'coral' },
  { title: 'Check in after exercise', body: 'Stop and cool down if you feel dizzy, faint, unusually short of breath, or have chest discomfort.', category: 'First aid', accent: 'coral' },
  { title: 'Use gloves when needed', body: 'Wear disposable gloves for contact with blood or body fluids, then wash your hands after removal.', category: 'First aid', accent: 'blue' },
  { title: 'Do not move a neck injury', body: 'Keep someone still after a serious fall or collision unless the area is immediately unsafe.', category: 'First aid', accent: 'coral' },
  { title: 'Keep emergency contacts ready', body: 'Add local emergency services, campus security, campus health, and a trusted contact to your phone.', category: 'Prevention', accent: 'sage' },
  { title: 'Use credible health sources', body: 'Prefer campus health, public health agencies, and licensed clinicians over viral posts or unverified advice.', category: 'Prevention', accent: 'blue' },
  { title: 'Check the expiry date', body: 'Review first-aid supplies and medicines each term, replacing anything expired, damaged, or empty.', category: 'Prevention', accent: 'sage' },
  { title: 'Wash reusable bottles', body: 'Clean bottles and lids regularly to prevent buildup, especially when they stay in a backpack.', category: 'Prevention', accent: 'blue' },
  { title: 'Do not share needles', body: 'Never share needles or injection equipment. Contact a health professional for confidential support.', category: 'Prevention', accent: 'coral' },
  { title: 'Know stroke signs', body: 'Face drooping, arm weakness, or speech trouble means act FAST and call emergency services immediately.', category: 'First aid', accent: 'coral' },
  { title: 'Chest pain is urgent', body: 'New or severe chest pressure, especially with sweating or shortness of breath, needs emergency assessment.', category: 'First aid', accent: 'coral' },
  { title: 'Ask a pharmacist', body: 'Pharmacists can help with common medicine questions, side effects, and safe over-the-counter choices.', category: 'Prevention', accent: 'sage' },
  { title: 'Make a care plan', body: 'If you have asthma, diabetes, or severe allergies, share an action plan with trusted roommates or friends.', category: 'Prevention', accent: 'blue' },
  { title: 'Trust your instincts', body: 'If something feels seriously wrong, seek help. It is always okay to ask a professional to assess you.', category: 'First aid', accent: 'coral' },
]

const answers = [
  { match: ['burn', 'scald'], title: 'For a minor burn', body: 'Cool the area under clean, cool running water for 20 minutes. Remove jewelry or clothing near the burn if it is not stuck. Do not use ice, butter, or creams. Seek urgent care for deep, extensive, electrical, chemical, or facial burns.' },
  { match: ['headache', 'head pain'], title: 'For a mild headache', body: 'Try water, a quiet space, a small meal if you have not eaten, and a screen break. Seek urgent help for a sudden severe headache, confusion, weakness, fever with a stiff neck, or a headache after a serious injury.' },
  { match: ['anxiety', 'stress', 'panic'], title: 'When stress feels intense', body: 'Sit somewhere safe and slow your breathing by making each exhale a little longer than the inhale. Contact a trusted person or campus counseling. If you may hurt yourself or cannot stay safe, contact emergency services or a crisis line now.' },
  { match: ['cut', 'bleed', 'bleeding'], title: 'For a cut or bleeding', body: 'Wash your hands, apply firm direct pressure with clean cloth or gauze, and keep pressure on. Call emergency services for heavy, spurting, or uncontrolled bleeding, or if the wound is deep.' },
  { match: ['cold', 'flu', 'sick', 'fever'], title: 'When you feel sick', body: 'Rest, drink fluids, and reduce close contact while you have contagious symptoms. Check campus health guidance. Seek urgent care for trouble breathing, confusion, severe dehydration, or a fever with serious symptoms.' },
]

function App() {
  const [tipIndex, setTipIndex] = useState(() => Math.floor(Math.random() * tips.length))
  const [secondsLeft, setSecondsLeft] = useState(15)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<{ title: string; body: string } | null>(null)
  const [activeTab, setActiveTab] = useState<'all' | Tip['category']>('all')

  const tip = tips[tipIndex]
  const visibleTips = useMemo(() => activeTab === 'all' ? tips : tips.filter((item) => item.category === activeTab), [activeTab])

  const showNextTip = () => {
    let nextIndex = Math.floor(Math.random() * tips.length)
    while (tips.length > 1 && nextIndex === tipIndex) nextIndex = Math.floor(Math.random() * tips.length)
    setTipIndex(nextIndex)
    setSecondsLeft(15)
  }

  const showPreviousTip = () => {
    setTipIndex((current) => (current - 1 + tips.length) % tips.length)
    setSecondsLeft(15)
  }

  useEffect(() => {
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => {
        if (current <= 1) {
          showNextTip()
          return 15
        }
        return current - 1
      })
    }, 1000)
    return () => window.clearInterval(timer)
  }, [tipIndex])

  const askMedi = () => {
    const normalized = question.trim().toLowerCase()
    const found = answers.find((item) => item.match.some((keyword) => normalized.includes(keyword)))
    setAnswer(found ?? {
      title: 'A starting point for your question',
      body: 'I can offer general educational guidance on common first aid, prevention, and wellbeing topics. For a personal diagnosis, medication change, or urgent concern, contact campus health or emergency services.',
    })
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="MediFlow Campus Care home">
          <span className="brand-mark"><HeartPulse size={20} strokeWidth={2.5} /></span>
          <span><strong>MediFlow</strong><small>Campus Care</small></span>
        </a>
        <div className="topbar-note"><span className="status-dot" /> Student wellness, made clearer</div>
        <button className="profile-button" aria-label="Open profile"><span>JD</span><ChevronRight size={16} /></button>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-line" /> YOUR EVERYDAY HEALTH COMPANION</p>
          <h1>Small steps.<br /><em>Better prepared.</em></h1>
          <p className="hero-subtitle">Practical first aid and wellbeing guidance for the moments campus life does not prepare you for.</p>
          <div className="hero-actions">
            <a className="primary-action" href="#tips">Explore tips <ArrowRight size={17} /></a>
            <a className="text-action" href="#ask">Ask Medi <MessageCircleQuestion size={17} /></a>
          </div>
        </div>
        <div className="hero-illustration" aria-hidden="true">
          <div className="sun-disc" />
          <div className="illustration-card card-back" />
          <div className="illustration-card card-front">
            <div className="illustration-top"><span className="pulse-icon"><HeartPulse size={22} /></span><span>CARE NOTE</span><span className="card-number">01</span></div>
            <div className="mini-wave" />
            <p>Keep calm.<br /><strong>Know what to do.</strong></p>
            <div className="card-foot"><span>MEDIFLOW / 2026</span><ShieldCheck size={16} /></div>
          </div>
          <div className="float-pill pill-one"><Lightbulb size={15} /> 60+ tips</div>
          <div className="float-pill pill-two"><span className="tiny-pulse" /> 24/7 support</div>
        </div>
      </section>

      <section className="stats-row" aria-label="MediFlow facts">
        <div><span className="stat-icon orange"><Stethoscope size={18} /></span><span><strong>60+</strong><small>care tips</small></span></div>
        <div><span className="stat-icon blue"><Clock3 size={18} /></span><span><strong>15 sec</strong><small>tip refresh</small></span></div>
        <div><span className="stat-icon green"><ShieldCheck size={18} /></span><span><strong>Student-first</strong><small>plain language</small></span></div>
        <p>For urgent situations, contact local emergency services.<br />MediFlow is an education tool, not a diagnosis.</p>
      </section>

      <section className="content-grid" id="tips">
        <div className="tip-column">
          <div className="section-heading"><div><p className="eyebrow">LIVE CARE NOTE</p><h2>A little knowledge<br /><em>goes a long way.</em></h2></div><span className="tip-count">{String(tipIndex + 1).padStart(2, '0')} / {tips.length}</span></div>
          <article className={`tip-card ${tip.accent}`}>
            <div className="tip-card-top"><span className="category-label"><span className="category-dot" /> {tip.category}</span><span className="auto-label"><TimerReset size={14} /> AUTO-ROTATES</span></div>
            <div className="tip-body"><span className="tip-number">{String(tipIndex + 1).padStart(2, '0')}</span><div><h3>{tip.title}</h3><p>{tip.body}</p></div></div>
            <div className="tip-card-bottom"><span><span className="timer-ring"><span style={{ '--progress': `${(secondsLeft / 15) * 360}deg` } as CSSProperties}>{secondsLeft}</span></span> next tip in <strong>{secondsLeft}s</strong></span><div className="tip-controls"><button onClick={showPreviousTip} aria-label="Previous tip"><ChevronLeft size={19} /></button><button onClick={showNextTip} aria-label="Next tip"><ChevronRight size={19} /></button></div></div>
          </article>
          <div className="tip-library-head"><div><p className="eyebrow">THE LIBRARY</p><h3>Browse the basics</h3></div><div className="filter-tabs" role="tablist">{(['all', 'First aid', 'Wellbeing', 'Prevention'] as const).map((tab) => <button key={tab} className={activeTab === tab ? 'active' : ''} onClick={() => setActiveTab(tab)} role="tab">{tab === 'all' ? 'All topics' : tab}</button>)}</div></div>
          <div className="tip-list">{visibleTips.slice(0, 6).map((item, index) => <button className="tip-list-item" key={`${item.title}-${index}`} onClick={() => setTipIndex(tips.indexOf(item))}><span className={`list-index ${item.accent}`}>{String(tips.indexOf(item) + 1).padStart(2, '0')}</span><span><strong>{item.title}</strong><small>{item.category}</small></span><ArrowRight size={16} /></button>)}</div>
        </div>

        <aside className="ask-panel" id="ask">
          <div className="ask-panel-head"><span className="bot-orbit"><Bot size={22} /></span><div><p className="eyebrow">QUICK GUIDANCE</p><h2>Ask Medi<span>.</span></h2></div><Sparkles className="sparkle" size={20} /></div>
          <p className="ask-intro">Have a basic health or first aid question? Get a clear starting point, then know when to reach a real professional.</p>
          <div className="question-box"><Search size={18} /><input value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && askMedi()} placeholder="Try “What should I do for a burn?”" aria-label="Ask a health question" /><button onClick={askMedi} aria-label="Send question"><ArrowRight size={18} /></button></div>
          <div className="suggestions"><span>Try asking</span><button onClick={() => setQuestion('What should I do for a burn?')}>burns</button><button onClick={() => setQuestion('I feel very stressed')}>stress</button><button onClick={() => setQuestion('How do I help a cut?')}>cuts</button></div>
          {answer ? <div className="answer-box"><div className="answer-title"><Bot size={16} /><strong>{answer.title}</strong></div><p>{answer.body}</p><span className="answer-note"><Info size={14} /> General education only</span></div> : <div className="ask-empty"><div className="empty-orbit"><MessageCircleQuestion size={22} /></div><p>Your answer will appear here.<br /><span>Medi is ready when you are.</span></p></div>}
          <div className="panel-foot"><span><ShieldCheck size={14} /> Private by design</span><a href="#tips">View all tips <ArrowRight size={14} /></a></div>
        </aside>
      </section>

      <footer><span>MEDIFLOW <b>/</b> CAMPUS CARE</span><span>Learn. Prepare. Look out for each other.</span></footer>
    </main>
  )
}

export default App
