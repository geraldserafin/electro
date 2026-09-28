// The note as a document: its look (the theme) and the pieces a note is made of — code, what the
// code printed, drawings, formulas. The note itself (main.typ) and its settings (config.typ) are
// written by the app (src/pdf/typst/document.ts).
#import "mitex/lib.typ": mi, mitex
#import "config.typ": config, formulas, bad

#let themes = (
  // like LaTeX: Computer Modern, justified, plain headings
  classic: (font: "New Computer Modern", accent: black, justify: true, code-fill: luma(246), radius: 2pt),
  // like the app: a sans, the yellow of the bolt, soft boxes
  modern: (font: "Inter", accent: rgb("#f5b100"), justify: false, code-fill: rgb("#f5f6f8"), radius: 6pt),
  // like a book: Libertinus, small caps, a dark red
  elegant: (font: "Libertinus Serif", accent: rgb("#7a1f3d"), justify: true, code-fill: rgb("#f8f6f2"), radius: 0pt),
)
#let theme = themes.at(config.theme)
// the colour of headings, links and rules: the one chosen, or the theme's
#let accent = if config.accent == auto { theme.accent } else { config.accent }
#let mono = "DejaVu Sans Mono"

// ------------------------------------------------------------------ the pieces

// formulas are LaTeX, read by mitex; one it cannot read shows as it was written
#let m(i) = if i in bad { raw(formulas.at(i)) } else { mi(formulas.at(i)) }
#let M(i) = if i in bad { block(raw(block: true, formulas.at(i))) } else { mitex(formulas.at(i)) }

// a drawing (a schematic, or what code drew): centred, never wider than the page
#let drawing(path, width) = block(breakable: false, above: 1.1em, below: 1.1em, width: 100%,
  layout(size => align(center, image(path, width: calc.min(width, size.width)))))

// a line of code with its number in front (settings: line numbers)
#let numbered(line) = box(width: 1.6em, align(right, text(fill: luma(160), str(line.number)))) + h(0.9em) + line.body

#let code(source) = block(width: 100%, fill: theme.code-fill, inset: (x: 10pt, y: 8pt), radius: theme.radius, {
  show raw.line: it => if config.code-lines { numbered(it) } else { it }
  raw(block: true, lang: "python", source)
})

#let output(s) = block(width: 100%, inset: (left: 10pt, y: 3pt), stroke: (left: 1.5pt + luma(205)),
  raw(block: true, s))

#let error(s) = block(width: 100%, inset: (left: 10pt, y: 3pt), stroke: (left: 1.5pt + rgb("#d93025")),
  text(fill: rgb("#b3261e"), raw(block: true, s)))

#let warning(body) = block(width: 100%, fill: rgb("#fef7e0"), inset: (x: 10pt, y: 7pt), radius: theme.radius,
  text(fill: rgb("#7a5200"))[⚠ #body])

// ------------------------------------------------------------------ the page

#let heading-number(it) = if it.numbering != none { counter(heading).display(it.numbering) + h(0.6em) }

// who wrote it and when, under the title: "Jan Kowalski · 28 września 2026"
#let byline() = (config.author, config.date).filter(x => x != none).join([ #sym.dot.c ])

#let title-block() = {
  let by = byline()
  if config.theme == "modern" {
    block(below: 1.8em, {
      text(size: 2.1em, weight: "bold", config.title)
      v(0.2em)
      line(length: 42pt, stroke: 3.5pt + accent)
      if by != none { v(0.1em); text(fill: luma(110), by) }
    })
  } else if config.theme == "elegant" {
    align(center, block(below: 2em, {
      text(size: 2em, smallcaps(config.title))
      v(0.7em, weak: true)
      line(length: 30%, stroke: 0.5pt + accent)
      if by != none { v(0.7em, weak: true); emph(by) }
    }))
  } else {
    align(center, block(below: 1.8em, {
      text(size: 1.75em, weight: "bold", fill: if config.accent == auto { black } else { accent }, config.title)
      if by != none { v(0.5em, weak: true); by }
    }))
  }
}

// the title at the top of the pages after the first (settings: header)
#let running-header() = context if counter(page).get().first() > 1 {
  set text(size: 0.8em, fill: luma(120))
  if config.theme == "elegant" { align(center, smallcaps(config.title)) } else { config.title }
  v(-0.55em)
  line(length: 100%, stroke: 0.4pt + luma(200))
}

// "2 / 7" at the bottom; none on a title page
#let page-number() = context if not (config.title-page and counter(page).get().first() == 1) {
  align(center, text(size: 0.85em, fill: luma(110),
    str(counter(page).get().first()) + " / " + str(counter(page).final().first())))
}

#let note(body) = {
  set document(title: config.title) if config.title != none
  set document(author: config.author) if config.author != none
  set page(
    paper: config.paper, flipped: config.flipped, margin: config.margin,
    header: if config.header and config.title != none { running-header() },
    footer: if config.page-numbers { page-number() },
  )
  set text(font: theme.font, size: config.size, lang: "pl")
  set par(
    justify: if config.justify == auto { theme.justify } else { config.justify },
    leading: config.spacing.leading, spacing: config.spacing.spacing,
  )
  show raw: set text(font: mono)
  // code in a sentence: on a light patch, as in the app
  show raw.where(block: false): it => box(fill: theme.code-fill, inset: (x: 2.5pt), outset: (y: 2.5pt), radius: 2pt, it)
  set heading(numbering: if config.numbering { "1.1." } else { none })
  show link: it => text(fill: if config.accent != auto { accent } else if config.theme == "classic" { rgb("#1a4d99") } else { accent.darken(20%) }, it)

  // tables: rules, not a grid; the header row bold
  set table(stroke: (_, y) => if y == 0 { (top: 0.8pt, bottom: 0.5pt) } else { (bottom: 0.3pt + luma(200)) }, inset: (x: 7pt, y: 5pt))
  show table.cell.where(y: 0): strong
  show table: set align(center)

  show heading: it => {
    if config.theme == "modern" {
      let size = if it.level == 1 { 1.3em } else if it.level == 2 { 1.12em } else { 1em }
      block(above: 1.5em, below: 0.8em, sticky: true, {
        if it.level == 1 {
          box(width: 3pt, height: 0.9em, fill: accent, baseline: 0.05em)
          h(8pt)
        }
        text(size: size, weight: "semibold", heading-number(it) + it.body)
      })
    } else if config.theme == "elegant" {
      let size = if it.level == 1 { 1.4em } else if it.level == 2 { 1.15em } else { 1em }
      block(above: 1.6em, below: 0.9em, sticky: true,
        text(size: size, weight: "regular", fill: if it.level == 1 { accent } else { black },
          heading-number(it) + smallcaps(it.body)))
    } else if config.accent != auto {
      text(fill: accent, it)
    } else {
      it
    }
  }
  // each top section from a new page (not the first: it follows the title)
  show heading.where(level: 1): it => {
    if config.section-breaks {
      context if query(heading.where(level: 1).before(it.location(), inclusive: false)).len() > 0 { pagebreak(weak: true) }
    }
    it
  }

  if config.title-page {
    // the title alone, a little above the middle of its page
    v(1fr)
    title-block()
    v(1.4fr)
    pagebreak()
  }
  // in columns: the text (the title goes across the page, over them)
  set page(columns: config.columns)
  set columns(gutter: 7mm)
  if config.title != none and not config.title-page {
    if config.columns > 1 { place(top, scope: "parent", float: true, clearance: 1.6em, block(width: 100%, below: 0pt, title-block())) } else { title-block() }
  }
  if config.outline {
    block(below: 2em, outline(title: "Spis treści", indent: auto))
  }
  body
}
