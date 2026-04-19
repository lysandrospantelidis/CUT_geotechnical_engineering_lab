# -*- coding: utf-8 -*-
# Shared data for Tkinter and Streamlit versions of the Rock Identification Key

APP_LINK = "https://cut-apps.streamlit.app/"

ORIGINAL_LINK = "http://www.minsocam.org/msa/collectors_corner/id/rock_key.htm"

WIKI_LINKS = {
    "MARBLE": "https://en.wikipedia.org/wiki/Marble",
    "BRECCIA": "https://en.wikipedia.org/wiki/Breccia",
    "CONGLOMERATE": "https://en.wikipedia.org/wiki/Conglomerate_(geology)",
    "LIMESTONE": "https://en.wikipedia.org/wiki/Limestone",
    "SHALE": "https://en.wikipedia.org/wiki/Shale",
    "SANDSTONE": "https://en.wikipedia.org/wiki/Sandstone",
    "OBSIDIAN": "https://en.wikipedia.org/wiki/Obsidian",
    "SCORIA": "https://en.wikipedia.org/wiki/Scoria",
    "PUMICE": "https://en.wikipedia.org/wiki/Pumice",
    "GABBRO": "https://en.wikipedia.org/wiki/Gabbro",
    "DIABASE": "https://en.wikipedia.org/wiki/Diabase",
    "BASALT": "https://en.wikipedia.org/wiki/Basalt",
    "DIORITE": "https://en.wikipedia.org/wiki/Diorite",
    "GRANITE": "https://en.wikipedia.org/wiki/Granite",
    "RHYOLITE": "https://en.wikipedia.org/wiki/Rhyolite",
    "SERPENTINITE": "https://en.wikipedia.org/wiki/Serpentinite",
    "SLATE": "https://en.wikipedia.org/wiki/Slate",
    "QUARTZITE": "https://en.wikipedia.org/wiki/Quartzite",
    "SCHIST": "https://en.wikipedia.org/wiki/Schist",
    "GNEISS": "https://en.wikipedia.org/wiki/Gneiss",
}

ROCK_INFO_EN = {
    "GNEISS": {"name":"GNEISS","type":"Metamorphic","minerals":"Almost always: feldspars, quartz, mica. Sometimes: kyanite, garnet, hornblende, tourmaline, magnetite, and many others.","look":"Usually light but can be dark. Looks like it has ribbons/bands of minerals. Grain size usually fairly coarse. Breaks into blocky pieces, not along layers. Crystals are lined up in layers (unlike randomly arranged granite). Tough and hard.","formation":"Formed from schist (which formed from fine-grained sedimentary rock, often shale) and also from some igneous rocks, especially granite; usually under great pressure from moving plates.","compare":"schist, granite"},
    "SCHIST": {"name":"SCHIST","type":"Metamorphic","minerals":"Quartz, feldspar, mica (muscovite, biotite). Sometimes: chlorite, garnet, hornblende, actinolite, kyanite, magnetite, pyrite, staurolite, tourmaline, and many others.","look":"Thin layers of mica (silvery to green to brown to black) or green to very dark green chlorite; often lens-like layers of quartz between mica layers. Layers may be wavy. Grain size medium to coarse. Splits easily along the mica layers (unlike gneiss).","formation":"Usually formed from shales (clay or sandy clay, sometimes with a little lime; sometimes volcanic rocks/sediments). Most often where ocean-floor rocks get crunched as plates push under/into/onto a continent.","compare":"gneiss, shale, slate, serpentinite"},
    "MARBLE": {"name":"MARBLE","type":"Metamorphic","minerals":"Calcite or dolomite (dolomitic marble). Sometimes: graphite, pyrite, mica, tremolite, and a few others.","look":"Often pure white, may be streaked/patchy gray, green, tan, or red. Fine- to very coarse-grained; crystals usually easy to see. Soft; does not scratch glass (quartzite may look like fine-grained marble but easily scratches glass). Powdered marble often fizzes with vinegar (dolomitic may not).","formation":"Forms from the metamorphism of limestones.","compare":"quartzite, limestone"},
    "QUARTZITE":{"name":"QUARTZITE","type":"Metamorphic","minerals":"Quartz; sometimes a little: mica, feldspar, magnetite, pyrite, ilmenite, garnet, and a few others.","look":"Pure quartzite is white; may be yellowish to reddish (iron) or rarely black (magnetite). Grains of sand may be seen with magnifier. Breaks through the grains (sandstone breaks around them). Very hard and easily scratches glass.","formation":"Most quartzite is metamorphosed sandstone.","compare":"marble, sandstone"},
    "SLATE":{"name":"SLATE","type":"Metamorphic","minerals":"Micas, feldspars, quartz (too small to recognize without a microscope). Sometimes contains pyrite.","look":"Black, gray, brownish red, bluish gray, or greenish gray. Very fine grained with thin, smooth, flat layers. Unlike shale, splits easily into thin flat pieces. Often will scratch glass, with a little difficulty.","formation":"Usually formed from clay sediments or shale that has been heated and put under pressure by plate collisions (lower grade than schist).","compare":"shale, schist, serpentinite"},
    "SERPENTINITE":{"name":"SERPENTINITE","type":"Metamorphic","minerals":"Mostly antigorite, amesite, lizardite. Sometimes: chrysotile (a type of asbestos), brucite, magnesite, chromite, magnetite and garnets; talc often found (serpentine alters to talc).","look":"Feels very slippery. More a broken rock than layered; ‘layers’ are flat plates of green rock (thin to >2 cm). Usually green to grayish-green; plates may have long scratch-like grooves; dull to nearly glassy.","formation":"Common where oceanic crust is pushed onto a continent. Peridotite at the bottom of oceanic plates is altered to serpentinite as pressure/temperature drop and water circulates. Also from peridotites that crystallize deep in the crust and later alter near surface.","compare":"diabase, gabbro, slate, schist"},
    "RHYOLITE":{"name":"RHYOLITE","type":"Igneous","minerals":"Quartz, feldspars; sometimes biotite, diopside, hornblende, zircon.","look":"Usually light colored (light gray, tan, reddish, greenish, brown). Fine-grained with scattered larger crystals (phenocrysts). May contain small gas pockets. Sometimes shows flow lines or bands.","formation":"Volcanic; rapid cooling of a silica-rich magma/lava. Pumice is a kind of rhyolite with a lot of tiny gas bubbles.","compare":"pumice, basalt"},
    "GRANITE":{"name":"GRANITE","type":"Igneous","minerals":"Quartz, feldspars (microcline, orthoclase, albite), biotite, muscovite; sometimes hornblende, augite, magnetite, zircon.","look":"Feldspars give most of the color (white–light gray–yellowish–pink). Quartz smoky gray/white. Black specks of biotite or hornblende; silvery/brownish muscovite common. Coarse to very coarse grained; crystals randomly arranged (unlike gneiss).","formation":"Forms deep in the crust from cooling silica-rich magma; slow cooling produces large crystals.","compare":"gneiss, diorite"},
    "DIORITE":{"name":"DIORITE","type":"Igneous","minerals":"Dark-colored plagioclase, hornblende, pyroxene; sometimes a little quartz; may contain light plagioclase but only a little.","look":"Looks like a dark-colored granite; usually medium to dark gray. Coarse grained (larger than rice). Little to no mica (and if any, dark).","formation":"Forms deep in the crust from cooling magma lacking much quartz/light minerals (vs granite).","compare":"granite, diabase"},
    "BASALT":{"name":"BASALT","type":"Igneous","minerals":"Plagioclase feldspars, augite, hypersthene, olivine.","look":"Dark gray to black; surface may turn yellow/brown with weathering. Fine grained; crystals microscopic or barely visible. Hard, tough; sometimes with gas bubbles (vesicular basalt).","formation":"Volcanic; magma rich in iron & magnesium and poor in silica erupts as lava and cools quickly (fine grained).","compare":"rhyolite, diabase, gabbro"},
    "DIABASE":{"name":"DIABASE","type":"Igneous","minerals":"Plagioclase feldspars, augite; sometimes hornblende, magnetite, olivine, glass.","look":"Dark green to black; weathered surfaces often brown. Medium grain size (visible without magnifier, smaller than rice). Tough, hard.","formation":"From Fe-Mg-rich, silica-poor magma injected near the surface (cools slower than basalt → larger crystals).","compare":"basalt, gabbro, diorite, serpentinite"},
    "GABBRO":{"name":"GABBRO","type":"Igneous","minerals":"Plagioclase feldspars, augite, hypersthene, olivine; sometimes magnetite, chromite, titanite, ilmenite.","look":"Dark green to black; weathered surface often brown. Large grain size (most grains larger than rice).","formation":"Cools and crystallizes deep below the surface from Fe-Mg-rich magma (same magma family as basalt/diabase; slower cooling → larger crystals).","compare":"basalt, diabase, serpentinite"},
    "PUMICE":{"name":"PUMICE","type":"Igneous","minerals":"Glass; mineral grains are unusual.","look":"Very light gray to medium gray; huge number of gas bubbles surrounded by thin volcanic glass; looks like a sponge; very light (often floats).","formation":"Explosively blown out of volcanoes from highly silicic, sticky magma; same magma type as rhyolite/granite.","compare":"scoria, rhyolite"},
    "SCORIA":{"name":"SCORIA","type":"Igneous","minerals":"Mainly a glass.","look":"Usually black, dark gray, brown, or dark green; glassy, smooth to rough; contains gas bubbles fewer but larger than pumice; moderately heavy.","formation":"Usually from the top of a lava flow; cools quickly before many crystals form.","compare":"pumice, basalt"},
    "OBSIDIAN":{"name":"OBSIDIAN","type":"Igneous","minerals":"Black glass.","look":"Usually black (sometimes slightly grayish/greenish); may include white ‘snowflakes’ or red swirls. Chips with conchoidal fracture (clam-shell like), often with semicircular ridges.","formation":"Volcanic; rapid cooling silica-rich lava so fast that crystals do not have time to form.","compare":""},
    "SANDSTONE":{"name":"SANDSTONE","type":"Sedimentary","minerals":"Quartz; sometimes feldspars, mica, glauconite (green), magnetite, garnet, rutile, ilmenite.","look":"Often red to brown, light gray to nearly white; sometimes yellow or green. Usually rounded grains of similar size; medium grained. Some show slight color layering.","formation":"Quartz sand deposited by rivers, waves, or wind (bars, beaches, dunes), then buried, compacted and cemented.","compare":"Arkose (pink/red, angular grains, >25% feldspar); Greywacke (black/dark green, coarse angular grains mixed with fine)."},
    "SHALE":{"name":"SHALE","type":"Sedimentary","minerals":"Clay minerals; sometimes quartz sand, pyrite, gypsum.","look":"Black, gray, red, brown, dark green, or blue. Fine grained (particles usually not seen). When moistened, smells like wet mud.","formation":"Clay sediments settle in quiet lakes/lagoons/bays/off-shore; buried and compacted; iron oxides often help cement.","compare":"slate, schist"},
    "LIMESTONE":{"name":"LIMESTONE","type":"Sedimentary","minerals":"Mostly calcite.","look":"Usually white, gray, tan, or yellow; may be red/black if impure. Fossils often present. Smooth to sugary; fine to medium grained. Powdered rock usually fizzes in vinegar. Unlike marble, not composed of visible crystals.","formation":"Most formed by chemical reaction in sea water (lime mud that settles); some from buried coral reefs. Related: Dolostone (dolomite) does not fizz as powder in vinegar.","compare":"marble"},
    "CONGLOMERATE":{"name":"CONGLOMERATE","type":"Sedimentary","minerals":"Mostly quartz (pebbles may be many rock types).","look":"Mixture of sand and different sizes of rounded pebbles (pebbles are key observation).","formation":"Sand and pebbles collect along shores or river banks; compacted by overlying sediments and cemented by dissolved material.","compare":"breccia"},
    "BRECCIA":{"name":"BRECCIA","type":"Sedimentary","minerals":"Cement mostly quartz; clasts can be almost any rock (often quartzite, granite, or other tough rocks).","look":"Like conglomerate, but clasts are jagged/blocky, not rounded.","formation":"Dry environments (deserts). Broken pieces pile up near source; with depth, compressed and cemented.","compare":"conglomerate"},
}
for k, u in WIKI_LINKS.items():
    if k in ROCK_INFO_EN:
        ROCK_INFO_EN[k]["link"] = u

ROCK_INFO_EL = {
    "GNEISS": {"name":"Γνεύσιος (Gneiss)","type":"Μεταμορφωμένο","minerals":"Σχεδόν πάντα: φελσπάθοι, χαλαζίας, μίκες. Μερικές φορές: κυανίτης, γρανάτης, ορβλενδίτης, τουρμαλίνη, μαγνητίτης και πολλά άλλα.","look":"Συνήθως ανοιχτόχρωμος αλλά μπορεί να είναι και σκουρόχρωμος. Δείχνει να έχει κορδέλες/ταινίες ορυκτών. Κοκκομετρία συνήθως αρκετά αδρή. Σπάει σε μπλοκώδη τεμάχια, όχι κατά μήκος στρώσεων. Οι κρύσταλλοι είναι ευθυγραμμισμένοι σε στρώσεις (σε αντίθεση με τον τυχαίο γρανίτη). Ανθεκτικός και σκληρός.","formation":"Σχηματίζεται από σχιστόλιθο και επίσης από κάποια πυριγενή πετρώματα, ειδικά γρανίτη· συνήθως υπό μεγάλη πίεση από την κίνηση λιθοσφαιρικών πλακών.","compare":"σχιστόλιθος, γρανίτης"},
    "SCHIST": {"name":"Σχιστόλιθος (Schist)","type":"Μεταμορφωμένο","minerals":"Χαλαζίας, φελσπάθοι, μίκες (μοσχοβίτης, βιοτίτης). Μερικές φορές: χλωρίτης, γρανάτης, ορβλενδίτης, ακτινόλιθος, κυανίτης, μαγνητίτης, πυρίτης, σταυρόλιθος, τουρμαλίνη και πολλά άλλα.","look":"Λεπτές στρώσεις μίκα ή χλωρίτη· συχνά φακοειδείς στρώσεις χαλαζία ανάμεσα στα επίπεδα μίκας. Οι στρώσεις μπορεί να είναι κυματιστές. Κοκκομετρία μεσαία έως αδρή. Διαχωρίζεται εύκολα κατά μήκος των στρώσεων μίκας.","formation":"Συνήθως σχηματίζεται από αργιλόλιθους ή αμμώδεις αργίλους· συνηθέστατα όπου τα πετρώματα του ωκεάνιου πυθμένα θρυμματίζονται καθώς οι πλάκες ωθούνται σε μια ήπειρο.","compare":"γνεύσιος, αργιλόλιθος, φυλλίτης, σερπεντινίτης"},
    "MARBLE": {"name":"Μάρμαρο (Marble)","type":"Μεταμορφωμένο","minerals":"Καλσίτης ή δολομίτης (δολομιτικό μάρμαρο). Μερικές φορές: γραφίτης, πυρίτης, μίκες, τρεμολίτης και λίγα άλλα.","look":"Συχνά καθαρά λευκό· μπορεί να έχει γκρι, πράσινες, μπεζ ή κόκκινες ραβδώσεις/κηλίδες. Λεπτόκοκκο έως πολύ αδρόκοκκο· οι κρύσταλλοι συνήθως διακρίνονται εύκολα. Μαλακό· δεν χαράζει το γυαλί. Η σκόνη μαρμάρου συχνά αφρίζει με ξύδι.","formation":"Σχηματίζεται από τη μεταμόρφωση ασβεστολίθων.","compare":"χαλαζιτικός ψαμμίτης, ασβεστόλιθος"},
    "QUARTZITE":{"name":"Χαλαζίτης / Quartzite","type":"Μεταμορφωμένο","minerals":"Χαλαζίας· μερικές φορές λίγο: μίκα, φελσπάθοι, μαγνητίτης, πυρίτης, ιλμενίτης, γρανάτης και λίγα άλλα.","look":"Ο καθαρός χαλαζίτης είναι λευκός· μπορεί να είναι κιτρινωπός έως κοκκινωπός ή σπάνια μαύρος. Σπάει διαμέσου των κόκκων. Πολύ σκληρός και χαράζει εύκολα γυαλί.","formation":"Ο περισσότερος χαλαζίτης είναι μεταμορφωμένος ψαμμίτης.","compare":"μάρμαρο, ψαμμίτης"},
    "SLATE":{"name":"Slate / Φυλλίτης","type":"Μεταμορφωμένο","minerals":"Μίκες, φελσπάθοι, χαλαζίας. Μερικές φορές περιέχει πυρίτη.","look":"Μαύρος, γκρίζος, κοκκινωπός καφέ, γαλαζωπός γκρι ή πρασινωπός γκρι. Πολύ λεπτόκοκκος με λεπτές, λείες, επίπεδες στρώσεις. Χωρίζεται εύκολα σε λεπτά επίπεδα τεμάχια.","formation":"Συνήθως σχηματίζεται από αργιλικές αποθέσεις ή αργιλόλιθους που θερμάνθηκαν και συμπιέστηκαν από συγκρούσεις πλακών.","compare":"αργιλόλιθος, σχιστόλιθος, σερπεντινίτης"},
    "SERPENTINITE":{"name":"Σερπεντινίτης (Serpentinite)","type":"Μεταμορφωμένο","minerals":"Κυρίως αντιγορίτης, αμεσίτης, λιζαρδίτης. Μερικές φορές: χρυσότιλος, βρουσίτης, μαγνησίτης, χρωμίτης, μαγνητίτης και γρανάτες.","look":"Νιώθεται πολύ ολισθηρός. Περισσότερο σπασμένο πέτρωμα παρά στρωματώδες. Συνήθως πράσινος έως πρασινογκρίζος.","formation":"Κοινός εκεί όπου ωκεάνιος φλοιός ωθείται πάνω σε ήπειρο. Επίσης από περιδοτίτες που αλλοιώνονται κοντά στην επιφάνεια.","compare":"διαβάσης, γάββρος, φυλλίτης, σχιστόλιθος"},
    "RHYOLITE":{"name":"Ρυόλιθος (Rhyolite)","type":"Πυριγενές","minerals":"Χαλαζίας, φελσπάθοι· μερικές φορές βιοτίτης, διοψίδιος, ορβλενδίτης, ζιρκόνιο.","look":"Συνήθως ανοιχτόχρωμος. Λεπτόκοκκος με διάσπαρτους μεγαλύτερους κρυστάλλους. Μπορεί να περιέχει μικρές φυσαλίδες αερίου.","formation":"Ηφαιστειακό· ταχεία ψύξη πλούσιου σε SiO₂ μάγματος/λάβας.","compare":"ελαφρόπετρα, βασάλτης"},
    "GRANITE":{"name":"Γρανίτης (Granite)","type":"Πυριγενές","minerals":"Χαλαζίας, φελσπάθοι, βιοτίτης, μοσχοβίτης· μερικές φορές ορβλενδίτης, αυγίτης, μαγνητίτης, ζιρκόνιο.","look":"Οι φελσπάθοι δίνουν το περισσότερο χρώμα. Αδρό έως πολύ αδρόκοκκος· οι κρύσταλλοι είναι τυχαία διατεταγμένοι.","formation":"Σχηματίζεται βαθιά στον φλοιό από ψύξη πλούσιου σε SiO₂ μάγματος.","compare":"γνεύσιος, διορίτης"},
    "DIORITE":{"name":"Διορίτης (Diorite)","type":"Πυριγενές","minerals":"Σκουρόχρωμα πλαγιόκλαστα, ορβλενδίτης, πυρόξενος· μερικές φορές λίγο χαλαζίας.","look":"Μοιάζει με σκουρόχρωμο γρανίτη· συνήθως μεσαίο έως σκούρο γκρι. Αδρόκοκκος.","formation":"Σχηματίζεται βαθιά από ψύξη μάγματος με λιγοστό χαλαζία/ανοιχτόχρωμα ορυκτά.","compare":"γρανίτης, διαβάσης"},
    "BASALT":{"name":"Βασάλτης (Basalt)","type":"Πυριγενές","minerals":"Πλαγιόκλαστα, αυγίτης, υπερσθενίτης, ολιβίνης.","look":"Σκούρο γκρι έως μαύρο. Λεπτόκοκκος· οι κρύσταλλοι είναι μικροσκοπικοί ή μόλις ορατοί.","formation":"Ηφαιστειακό· μάγμα πλούσιο σε Fe και Mg και φτωχό σε SiO₂ εκρήγνυται ως λάβα και ψύχεται γρήγορα.","compare":"ρυόλιθος, διαβάσης, γάββρος"},
    "DIABASE":{"name":"Διαβάσης (Diabase)","type":"Πυριγενές","minerals":"Πλαγιόκλαστα, αυγίτης· μερικές φορές ορβλενδίτης, μαγνητίτης, ολιβίνης, υαλώδης φάση.","look":"Σκούρο πράσινο έως μαύρο. Μεσαίου μεγέθους κόκκοι. Σκληρός, ανθεκτικός.","formation":"Από Fe–Mg πλούσιο, SiO₂ φτωχό μάγμα που εγχέεται κοντά στην επιφάνεια.","compare":"βασάλτης, γάββρος, διορίτης, σερπεντινίτης"},
    "GABBRO":{"name":"Γάββρος (Gabbro)","type":"Πυριγενές","minerals":"Πλαγιόκλαστα, αυγίτης, υπερσθενίτης, ολιβίνης· μερικές φορές μαγνητίτης, χρωμίτης, τιτανίτης, ιλμενίτης.","look":"Σκούρο πράσινο έως μαύρο. Μεγάλο μέγεθος κόκκων.","formation":"Ψύχεται και κρυσταλλώνεται βαθιά κάτω από την επιφάνεια από μάγμα πλούσιο σε Fe–Mg.","compare":"βασάλτης, διαβάσης, σερπεντινίτης"},
    "PUMICE":{"name":"Ελαφρόπετρα (Pumice)","type":"Πυριγενές","minerals":"Υαλώδης μάζα· κρύσταλλοι σπάνιοι.","look":"Πολύ ανοιχτό έως μεσαίο γκρι· τεράστιος αριθμός φυσαλίδων αερίου. Πολύ ελαφριά.","formation":"Εκτινάσσεται εκρηκτικά από ηφαίστεια από ιδιαίτερα πυριτικό, ιξώδες μάγμα.","compare":"σκωρία, ρυόλιθος"},
    "SCORIA":{"name":"Σκωρία (Scoria)","type":"Πυριγενές","minerals":"Κυρίως υαλώδης μάζα.","look":"Συνήθως μαύρη, σκούρο γκρι, καφέ ή σκούρο πράσινη· υαλώδης· περιέχει φυσαλίδες λιγότερες αλλά μεγαλύτερες από της ελαφρόπετρας.","formation":"Συνήθως από την κορυφή ροής λάβας· ψύχεται γρήγορα πριν σχηματιστούν πολλοί κρύσταλλοι.","compare":"ελαφρόπετρα, βασάλτης"},
    "OBSIDIAN":{"name":"Οψιδιανός (Obsidian)","type":"Πυριγενές","minerals":"Μαύρο γυαλί.","look":"Συνήθως μαύρος· μπορεί να έχει λευκές χιονονιφάδες ή ερυθρές ραβδώσεις. Θραύεται κογχυλοειδώς.","formation":"Ηφαιστειακό· ταχύτατη ψύξη πλούσιας σε SiO₂ λάβας.","compare":""},
    "SANDSTONE":{"name":"Ψαμμίτης (Sandstone)","type":"Ιζηματογενές","minerals":"Χαλαζίας· μερικές φορές φελσπάθοι, μίκες, γλαυκονίτης, μαγνητίτης, γρανάτης, ρουτίλιο, ιλμενίτης.","look":"Συχνά κόκκινος έως καφέ, ανοιχτό γκρι έως σχεδόν λευκό. Συνήθως στρογγυλεμένοι κόκκοι παρόμοιου μεγέθους.","formation":"Χαλαζιακή άμμος που αποτίθεται από ποτάμια, κύματα ή άνεμο, κατόπιν θάβεται, συμπιέζεται και τσιμεντώνεται.","compare":"Arkose, Greywacke"},
    "SHALE":{"name":"Αργιλόλιθος (Shale)","type":"Ιζηματογενές","minerals":"Αργιλικά ορυκτά· μερικές φορές χαλαζιακή άμμος, πυρίτης, γύψος.","look":"Μαύρος, γκρίζος, κόκκινος, καφέ, σκούρο πράσινος ή μπλε. Λεπτόκοκκος. Όταν υγρανθεί, μυρίζει βρεγμένη λάσπη.","formation":"Αργιλικές αποθέσεις καθιζάνουν σε ήρεμες λίμνες/λιμνοθάλασσες/κόλπους και στη συνέχεια θάβονται και συμπιέζονται.","compare":"φυλλίτης, σχιστόλιθος"},
    "LIMESTONE":{"name":"Ασβεστόλιθος (Limestone)","type":"Ιζηματογενές","minerals":"Κυρίως καλσίτης.","look":"Συνήθως λευκός, γκρίζος, μπεζ ή κιτρινωπός. Συχνά περιέχει απολιθώματα. Η σκόνη του συνήθως αφρίζει με ξύδι.","formation":"Ο περισσότερος σχηματίζεται με χημική αντίδραση σε θαλάσσιο νερό ή από θαμμένους κοραλλιογενείς υφάλους.","compare":"μάρμαρο"},
    "CONGLOMERATE":{"name":"Κροκαλοπαγές (Conglomerate)","type":"Ιζηματογενές","minerals":"Κυρίως χαλαζίας.","look":"Μείγμα άμμου και διαφορετικών μεγεθών από στρογγυλεμένες κροκάλες.","formation":"Άμμος και κροκάλες συσσωρεύονται κατά μήκος ακτών ή όχθεων ποταμών και τσιμεντώνονται.","compare":"βρέτσια"},
    "BRECCIA":{"name":"Βρέτσια (Breccia)","type":"Ιζηματογενές","minerals":"Τσιμέντο κυρίως χαλαζιακό· τα κλάστα μπορεί να είναι σχεδόν οποιοδήποτε πέτρωμα.","look":"Όπως το κροκαλοπαγές, αλλά τα κλάστα είναι γωνιώδη/μπλοκώδη, όχι στρογγυλεμένα.","formation":"Ξηρά περιβάλλοντα· τα κομμάτια στοιβάζονται κοντά στην πηγή και με το βάθος συμπιέζονται και τσιμεντώνονται.","compare":"κροκαλοπαγές"},
}
for k, u in WIKI_LINKS.items():
    if k in ROCK_INFO_EL:
        ROCK_INFO_EL[k]["link"] = u

NODES_EN = {
    "1":{"text":"Is the rock made of crystal grains?","explanation":"Does it have many flat, shiny faces—maybe tiny to small—that reflect light like little mirrors? You may need a magnifier.","yes":"2","yes_text":"The rock is made of crystal grains with flat shiny surfaces.","no":"3","no_text":"There are no (or not many) shiny, flat, crystal grains."},
    "2":{"text":"Does the rock have both layers and crystal grains?","explanation":"Look carefully for layers, especially along the edges.","yes":"4","yes_text":"The rock has both layers and crystals.","no":"5","no_text":"The rock has crystals, but it has no layers."},
    "3":{"text":"Does the rock have layers but not crystal grains?","explanation":"Look carefully for layers, especially along the edges.","yes":"11","yes_text":"The rock has layers; crystal grains are not visible.","no":"12","no_text":"No layers; no visible crystal grains."},
    "4":{"text":"Do the layers look like ribbons/bands of minerals and is the rock blocky?","explanation":"Bands may be straight or wavy. The rock breaks into blocky chunks, not along the layers.","yes":"GNEISS","yes_text":"Crystals with ribbon-like layers → GNEISS.","no":"SCHIST","no_text":"Thin micaceous layers → SCHIST."},
    "5":{"text":"Is the entire rock mostly light colored compared to other rocks?","explanation":"Look at the whole rock, not just individual grains.","yes":"6","yes_text":"Mostly light colored, crystalline, no layers.","no":"7","no_text":"Mostly medium gray to very dark minerals."},
    "6":{"text":"Can you scratch glass with the rock?","explanation":"If yes, the rock is hard; if no, soft. Keep glass flat on desk; drag a point ~2 cm carefully.","yes":"9","yes_text":"Scratches glass (hard).","no":"MARBLE","no_text":"Does not scratch glass → MARBLE."},
    "7":{"text":"Is the rock mostly light to medium gray (not very dark gray or black)?","explanation":"","yes":"DIORITE","yes_text":"Light-to-medium gray, crystalline, no layers → DIORITE.","no":"8","no_text":"Mostly very dark gray or black."},
    "8":{"text":"Can you see crystal grains without a magnifier in most/all of the rock?","explanation":"","yes":"10","yes_text":"Coarse or medium grained.","no":"BASALT","no_text":"Fine grained → BASALT."},
    "9":{"text":"Can you see crystal grains without a magnifier in most/all of the rock?","explanation":"","yes":"GRANITE","yes_text":"Medium or coarse, light colored → GRANITE.","no":"RHYOLITE","no_text":"Mostly fine, light colored → RHYOLITE."},
    "10":{"text":"Is the rock coarse grained (grains ≥ rice)?","explanation":"If grains smaller than rice but visible → medium grained.","yes":"GABBRO","yes_text":"Coarse, dark, no layers → GABBRO.","no":"DIABASE","no_text":"Medium, dark, no layers → DIABASE."},
    "11":{"text":"Using a steel nail, can you scrape grains of sand off the rock?","explanation":"Hold over clean paper; scrape hard; rub finger—feel sand?","yes":"SANDSTONE","yes_text":"Made of sand → SANDSTONE.","no":"13","no_text":"Not made of sand."},
    "12":{"text":"Does the rock have gas bubbles in it?","explanation":"Look for rounded/elongated holes (vesicles); tiny to pea sized.","yes":"15","yes_text":"Has gas bubbles.","no":"17","no_text":"No gas bubbles."},
    "13":{"text":"Mostly one mineral and many thin flat layers (< ~2 mm)?","explanation":"","yes":"SLATE","yes_text":"Many thin flat layers → SLATE.","no":"14","no_text":"Layers thicker or different."},
    "14":{"text":"Definitely green in color and slippery to the touch?","explanation":"","yes":"SERPENTINITE","yes_text":"Green & slippery → SERPENTINITE.","no":"SHALE","no_text":"Not green & slippery → SHALE."},
    "15":{"text":"Light in weight and mostly light colored (probably gray)?","explanation":"","yes":"PUMICE","yes_text":"Light, frothy → PUMICE.","no":"16","no_text":"Heavier/darker with larger bubbles."},
    "16":{"text":"Dark colored, glassy, with gas bubbles (some jagged/sharp points)?","explanation":"","yes":"SCORIA","yes_text":"Glassy, vesicular, dark → SCORIA.","no":"BASALT","no_text":"Gray/black with a few gas pockets, not glassy → BASALT."},
    "17":{"text":"Does it look like black glass with no bubbles?","explanation":"May have white ‘snowflakes’ or reddish bands.","yes":"OBSIDIAN","yes_text":"Black volcanic glass → OBSIDIAN.","no":"18","no_text":"Does not look like black glass."},
    "18":{"text":"Using a steel nail, can sand be scraped off the rock?","explanation":"","yes":"19","yes_text":"Sand can be scraped off.","no":"20","no_text":"Sand cannot be scraped off."},
    "19":{"text":"Does the rock contain sand AND larger pieces/pebbles?","explanation":"","yes":"22","yes_text":"Sand + pebbles.","no":"SANDSTONE","no_text":"Sand only → SANDSTONE."},
    "20":{"text":"Can the rock scratch glass?","explanation":"If yes, it’s hard.","yes":"21","yes_text":"Scratches glass.","no":"LIMESTONE","no_text":"Does not scratch glass, no visible crystals → LIMESTONE."},
    "21":{"text":"Is the rock white, yellowish, tan, or reddish?","explanation":"","yes":"QUARTZITE","yes_text":"White/yellowish/tan/reddish and hard → QUARTZITE.","no":"BASALT","no_text":"Black/gray → BASALT."},
    "22":{"text":"Are the larger pieces rounded pebbles (not blocky/jagged)?","explanation":"","yes":"CONGLOMERATE","yes_text":"Rounded pebbles → CONGLOMERATE.","no":"BRECCIA","no_text":"Jagged/blocky pieces → BRECCIA."},
}

NODES_EL = {
    "1":{"text":"Το πέτρωμα αποτελείται από κρυσταλλικούς κόκκους;","explanation":"Έχει πολλές επίπεδες, γυαλιστερές επιφάνειες που αντανακλούν το φως σαν μικρούς καθρέφτες; Ίσως χρειαστείς μεγεθυντικό φακό.","yes":"2","yes_text":"Κρυσταλλικοί κόκκοι με επίπεδες γυαλιστερές επιφάνειες.","no":"3","no_text":"Δεν υπάρχουν ή υπάρχουν λίγοι γυαλιστεροί, επίπεδοι, κρυσταλλικοί κόκκοι."},
    "2":{"text":"Έχει το πέτρωμα και στρώσεις και κρυσταλλικούς κόκκους;","explanation":"Κοίτα προσεκτικά για στρώσεις, ειδικά κατά μήκος των ακμών.","yes":"4","yes_text":"Στρώσεις + κρύσταλλοι.","no":"5","no_text":"Κρύσταλλοι χωρίς στρώσεις."},
    "3":{"text":"Έχει στρώσεις αλλά όχι κρυσταλλικούς κόκκους;","explanation":"Κοίτα προσεκτικά στις ακμές.","yes":"11","yes_text":"Στρώσεις – οι κρύσταλλοι δεν φαίνονται.","no":"12","no_text":"Χωρίς στρώσεις, χωρίς ορατούς κρυστάλλους."},
    "4":{"text":"Μοιάζουν οι στρώσεις με κορδέλες/ταινίες ορυκτών και το πέτρωμα είναι μπλοκώδες;","explanation":"Οι ταινίες μπορεί να είναι ευθείες ή κυματιστές. Το πέτρωμα σπάει σε μπλοκώδη τεμάχια, όχι κατά μήκος των στρώσεων.","yes":"GNEISS","yes_text":"Ταινιωτές στρώσεις → ΓΝΕΥΣΙΟΣ.","no":"SCHIST","no_text":"Λεπτές φυλλώσεις μίκας → ΣΧΙΣΤΟΛΙΘΟΣ."},
    "5":{"text":"Είναι το πέτρωμα κυρίως ανοιχτόχρωμο σε σχέση με άλλα;","explanation":"Δες το σύνολο, όχι μεμονωμένους κόκκους.","yes":"6","yes_text":"Ανοιχτόχρωμο, κρυσταλλικό, χωρίς στρώσεις.","no":"7","no_text":"Κυρίως μεσαίο γκρι έως πολύ σκούρο."},
    "6":{"text":"Χαράζει το πέτρωμα γυαλί;","explanation":"Αν ναι, είναι σκληρό· αν όχι, μαλακό.","yes":"9","yes_text":"Χαράζει γυαλί.","no":"MARBLE","no_text":"Δεν χαράζει → ΜΑΡΜΑΡΟ."},
    "7":{"text":"Είναι κυρίως ανοιχτό έως μεσαίο γκρι;","explanation":"","yes":"DIORITE","yes_text":"Ανοιχτό–μεσαίο γκρι, κρυσταλλικό, χωρίς στρώσεις → ΔΙΟΡΙΤΗΣ.","no":"8","no_text":"Κυρίως πολύ σκούρο γκρι ή μαύρο."},
    "8":{"text":"Βλέπεις κρυσταλλικούς κόκκους χωρίς φακό;","explanation":"","yes":"10","yes_text":"Αδρό ή μεσαίο μέγεθος κόκκων.","no":"BASALT","no_text":"Λεπτόκοκκο → ΒΑΣΑΛΤΗΣ."},
    "9":{"text":"Βλέπεις κρυσταλλικούς κόκκους χωρίς φακό;","explanation":"","yes":"GRANITE","yes_text":"Μεσαίο/αδρό, ανοιχτόχρωμο → ΓΡΑΝΙΤΗΣ.","no":"RHYOLITE","no_text":"Λεπτόκοκκο, ανοιχτόχρωμο → ΡΥΟΛΙΘΟΣ."},
    "10":{"text":"Είναι το πέτρωμα αδρόκοκκο (κόκκοι ≥ κόκκος ρυζιού);","explanation":"Αν οι κόκκοι είναι ορατοί αλλά μικρότεροι του ρυζιού → μεσαίου κόκκου.","yes":"GABBRO","yes_text":"Αδρό, σκούρο, χωρίς στρώσεις → ΓΑΒΒΡΟΣ.","no":"DIABASE","no_text":"Μεσαίο, σκούρο, χωρίς στρώσεις → ΔΙΑΒΑΣΗΣ."},
    "11":{"text":"Με ατσάλινο καρφί, μπορείς ξύνοντας να βγάλεις κόκκους άμμου;","explanation":"Κράτησε πάνω από καθαρό χαρτί· ξύσε δυνατά· τρίψε με δάχτυλο — νιώθεις άμμο;","yes":"SANDSTONE","yes_text":"Από άμμο → ΨΑΜΜΙΤΗΣ.","no":"13","no_text":"Όχι άμμος."},
    "12":{"text":"Έχει το πέτρωμα φυσαλίδες αερίων;","explanation":"Στρογγυλές/επιμήκεις οπές.","yes":"15","yes_text":"Έχει φυσαλίδες.","no":"17","no_text":"Χωρίς φυσαλίδες."},
    "13":{"text":"Κυρίως ένα ορυκτό και πολλές λεπτές επίπεδες στρώσεις (< ~2 mm);","explanation":"","yes":"SLATE","yes_text":"Πολλές λεπτές επίπεδες στρώσεις → SLATE.","no":"14","no_text":"Πιο παχιές/διαφορετικές στρώσεις."},
    "14":{"text":"Σίγουρα πράσινο στο χρώμα και ολισθηρό στην αφή;","explanation":"","yes":"SERPENTINITE","yes_text":"Πράσινο & ολισθηρό → ΣΕΡΠΕΝΤΙΝΙΤΗΣ.","no":"SHALE","no_text":"Όχι πράσινο & ολισθηρό → ΑΡΓΙΛΟΛΙΘΟΣ."},
    "15":{"text":"Ελαφρύ στο βάρος και κυρίως ανοιχτόχρωμο;","explanation":"","yes":"PUMICE","yes_text":"Ελαφρύ, αφρώδες → ΕΛΑΦΡΟΠΕΤΡΑ.","no":"16","no_text":"Βαρύτερο/σκοτεινό με μεγαλύτερες φυσαλίδες."},
    "16":{"text":"Σκουρόχρωμο, υαλώδες, με φυσαλίδες;","explanation":"","yes":"SCORIA","yes_text":"Υαλώδες, κυστιτικό, σκούρο → ΣΚΩΡΙΑ.","no":"BASALT","no_text":"Γκρι/μαύρο με λίγες κυστίδες, όχι υαλώδες → ΒΑΣΑΛΤΗΣ."},
    "17":{"text":"Μοιάζει με μαύρο γυαλί χωρίς φυσαλίδες;","explanation":"Μπορεί να έχει λευκές χιονονιφάδες ή ερυθρές ζώνες.","yes":"OBSIDIAN","yes_text":"Μαύρο ηφαιστειακό γυαλί → ΟΨΙΔΙΑΝΟΣ.","no":"18","no_text":"Δεν μοιάζει με μαύρο γυαλί."},
    "18":{"text":"Με ατσάλινο καρφί, μπορεί να βγει άμμος από το πέτρωμα;","explanation":"","yes":"19","yes_text":"Βγαίνει άμμος.","no":"20","no_text":"Δεν βγαίνει άμμος."},
    "19":{"text":"Περιέχει άμμο ΚΑΙ μεγαλύτερα κομμάτια/κροκάλες;","explanation":"","yes":"22","yes_text":"Άμμος + κροκάλες.","no":"SANDSTONE","no_text":"Μόνο άμμος → ΨΑΜΜΙΤΗΣ."},
    "20":{"text":"Μπορεί το πέτρωμα να χαράξει γυαλί;","explanation":"Αν ναι, είναι σκληρό.","yes":"21","yes_text":"Χαράζει γυαλί.","no":"LIMESTONE","no_text":"Δεν χαράζει γυαλί, χωρίς ορατούς κρυστάλλους → ΑΣΒΕΣΤΟΛΙΘΟΣ."},
    "21":{"text":"Είναι το πέτρωμα λευκό, κιτρινωπό, μπεζ ή ερυθρωπό;","explanation":"","yes":"QUARTZITE","yes_text":"Λευκό/κιτρινωπό/μπεζ/ερυθρωπό & σκληρό → ΧΑΛΑΖΙΤΗΣ.","no":"BASALT","no_text":"Μαύρο/γκρι → ΒΑΣΑΛΤΗΣ."},
    "22":{"text":"Τα μεγαλύτερα τεμάχια είναι στρογγυλεμένες κροκάλες;","explanation":"","yes":"CONGLOMERATE","yes_text":"Στρογγυλεμένες κροκάλες → ΚΡΟΚΑΛΟΠΑΓΕΣ.","no":"BRECCIA","no_text":"Γωνιώδη/μπλοκώδη τεμάχια → ΒΡΕΤΣΙΑ."},
}

UI_STR = {
    "el": {
        "title":"Κλειδί Αναγνώρισης Πετρωμάτων",
        "yes":"ΝΑΙ", "no":"ΟΧΙ",
        "back":"⟵ Πίσω", "home":"Αρχή",
        "portal":"CUT Apps", "info":"ℹ Πληροφορίες Πέτρας", "wiki":"Wikipedia", "orig":"Αρχικό Rock Key",
        "help_menu":"Βοήθεια", "help_defs":"Βοήθεια: Ορισμοί", "about":"Σχετικά",
        "intro_title":"Rock Identification Key",
        "intro_body":"Η παρούσα εφαρμογή δεν αντικαθιστά το αρχικό έργο. Προσφέρει μόνο μια web app και μια exe έκδοση του ‘The Rock Identification Key’ του Don Peck. Η αναγνώριση γίνεται βήμα-βήμα, ακολουθώντας το αρχικό δέντρο αποφάσεων, με βάση ορατά χαρακτηριστικά όπως υφή, στρώσεις, σκληρότητα, χρώμα και φυσαλίδες.",
        "orig_btn":"Άνοιγμα αρχικής σελίδας Don Peck",
        "questions_header":"Ερωτήσεις ΝΑΙ/ΟΧΙ",
        "result_header":"Αποτέλεσμα: Ταυτοποίηση Πεδίου",
        "note":"Σημείωση: η εφαρμογή ξεκινά αμέσως από την πρώτη ερώτηση του αρχικού κλειδιού.",
        "gloss":"Βασικοί ορισμοί:\n\n• Κρύσταλλοι: κόκκοι με επίπεδες γυαλιστερές έδρες.\n• Κόκκοι: στρογγυλοί ή οδοντωτοί, χωρίς επίπεδες έδρες.\n• Κοκκομετρία: αδρό, μεσαίο, λεπτό.\n• Στρώσεις/φυλλώσεις: εναλλαγές ταινιών/χρωμάτων/μεγεθών κόκκων.\n• Κυστίδες: οπές από παγιδευμένα αέρια.",
        "img_missing":"(Δεν βρέθηκε εικόνα στο ίδιο folder.)",
        "info_text":"Όνομα: {name}\nΤύπος πετρώματος: {type}\n\nΑπό ποια ορυκτά αποτελείται:\n{minerals}\n\nΠώς φαίνεται:\n{look}\n\nΠώς σχηματίστηκε:\n{formation}\n\nΣύγκρινε με:\n{compare}",
        "lang_label":"Γλώσσα:",
        "about_text":"Το πρόγραμμα προσφέρει μόνο web app και exe έκδοση του The Rock Identification Key του Don Peck. Δεν αποτελεί νέο αλγόριθμο ταυτοποίησης.",
        "close":"Κλείσιμο"
    },
    "en": {
        "title":"Rock Identification Key",
        "yes":"YES", "no":"NO",
        "back":"⟵ Back", "home":"Home",
        "portal":"CUT Apps", "info":"ℹ Rock Info", "wiki":"Wikipedia", "orig":"Original Rock Key",
        "help_menu":"Help", "help_defs":"Help: Definitions", "about":"About",
        "intro_title":"Rock Identification Key",
        "intro_body":"This program does not replace the original work. It only offers a web app and an exe version of ‘The Rock Identification Key’ by Don Peck. Identification is carried out step by step using the original decision tree, based on observable properties such as texture, layering, hardness, color, and vesicles.",
        "orig_btn":"Open Don Peck original page",
        "questions_header":"YES/NO Questions",
        "result_header":"Result: Field Identification",
        "note":"Note: the application starts directly from the first question of the original key.",
        "gloss":"Basic definitions:\n\n• Crystals: grains with flat shiny faces.\n• Grains: rounded or jagged, not flat-faced.\n• Grain size: coarse, medium, fine.\n• Layers/Foliation: alternating bands/colors/grain sizes.\n• Vesicles: holes from trapped gases.",
        "img_missing":"(No image found in the same folder.)",
        "info_text":"Name: {name}\nRock type: {type}\n\nWhat minerals:\n{minerals}\n\nWhat does it look like:\n{look}\n\nHow was it formed:\n{formation}\n\nCompare to:\n{compare}",
        "lang_label":"Language:",
        "about_text":"This program only offers a web app and an exe version of The Rock Identification Key by Don Peck. It is not a new identification algorithm.",
        "close":"Close"
    }
}

