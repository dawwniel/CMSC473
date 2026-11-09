-- CIX Library pilot. Run once in Studio plugin context:
-- require(game.ServerStorage.Prompt2Particles.CIXPilot).build()
-- require(game.ServerStorage.Prompt2Particles.CIXPilot).focus("N018")

local Pilot = {}

local Workspace = game:GetService("Workspace")
local PluginGuiService = game:GetService("PluginGuiService")

local effects = {
	{"N018", "FireFlames", "Fire", "Particle", "Fire1", "flame", {255, 145, 55}, "A small orange fire flickers and sends flame shapes upward."},
	{"N019", "SmokeMist", "Smoke", "Particle", "Smoke3", "smoke", {175, 180, 188}, "A soft gray smoke plume drifts upward and thins out."},
	{"N020", "CloudDrift", "Cloud", "Particle", "Cloud4", "cloud", {235, 239, 244}, "Pale clouds drift slowly across the air and fade."},
	{"N021", "DebrisBurst", "Debris", "Particle", "Rock1", "rock", {160, 164, 172}, "A burst of small gray rocks flies outward and falls."},
	{"N022", "FallingLeaves", "Leaves", "Particle", "Leaf1", "leaf", {232, 155, 64}, "Orange leaves tumble downward in a gentle breeze."},
	{"N023", "DustClouds", "Dust", "Particle", "Powder1", "dust", {181, 160, 130}, "A dusty impact throws a brown cloud outward before it fades."},
	{"N024", "ImpactSparks", "Sparks", "Particle", "Spark1", "spark", {255, 190, 93}, "A quick impact throws tiny golden sparks in every direction."},
	{"N025", "ElectricPulses", "Electric", "Particle", "Shockwave1", "ring", {92, 183, 255}, "A blue electric ring flashes and expands from the center."},
	{"N026", "SwordSlashes", "Slash", "Particle", "Slash1", "slash", {185, 222, 255}, "A pale blue crescent slash flashes and fades."},
	{"N027", "ImpactFlashes", "Impact", "Particle", "Impact1", "impact", {255, 229, 170}, "A sharp golden impact flash appears and disappears quickly."},
	{"N028", "SnowFlurry", "Snow", "Particle", "Snowflake3", "snow", {224, 241, 255}, "Icy snowflakes fall slowly and turn as they descend."},
	{"N029", "HealthHearts", "Healing", "Particle", "Heart1", "hearts", {255, 120, 164}, "Soft pink hearts float upward and fade away."},
	{"N030", "PortalRing", "Portal", "Particle", "FireCircle1", "fireRing", {255, 80, 22}, "A fiery orange portal ring expands and burns out."},
	{"N031", "WaterBubbles", "Water", "Particle", "Bubble1", "bubble", {181, 231, 255}, "Clear bubbles rise gently through water."},
	{"N032", "WaterBubbles", "Water", "Particle", "Bubble8", "foam", {180, 235, 255}, "Clusters of pale bubbles drift upward and fade."},
	{"N033", "MagicCircles", "Magic", "Particle", "MagicCircle1", "sigil", {114, 195, 255}, "A blue magic circle glows and slowly turns in place."},
	{"N034", "MagicCircles", "Magic", "Particle", "MagicCircle11", "sigil", {192, 137, 255}, "A violet compass-like sigil rotates slowly before fading."},
	{"N035", "PoisonBurst", "Poison", "Particle", "Toxic1", "toxic", {118, 222, 69}, "Green biohazard symbols rise and vanish."},
	{"N036", "LightningSparks", "Lightning", "Particle", "Lightning3", "arcs", {125, 208, 255}, "Short blue lightning arcs flicker and scatter outward."},
	{"N037", "CosmicSparks", "Cosmic", "Particle", "Star8", "stars", {188, 234, 255}, "Tiny blue-white stars rise and twinkle."},
	{"N038", "FireFlicker", "Fire", "FlipBook", "Fire6", "animatedFire", {255, 146, 67}, "Animated orange flame wisps rise and flicker."},
	{"N039", "SmokePuffs", "Smoke", "FlipBook", "Smoke1", "animatedSmoke", {177, 183, 193}, "Animated gray smoke puffs swell and drift upward."},
	{"N040", "LightningStrikes", "Lightning", "FlipBook", "Lightning1", "animatedStrike", {168, 222, 255}, "A branching blue lightning strike flashes once."},
	{"N041", "ExplosionBursts", "Explosion", "FlipBook", "Explosion1", "animatedExplosion", {255, 169, 80}, "A fiery explosion blooms and dissipates in one burst."},
	{"N042", "BleedSplatter", "Blood", "FlipBook", "Blood1", "animatedBlood", {214, 45, 53}, "A red blood splatter spreads and fades after an impact."},
	{"N043", "WaterRipples", "Water", "FlipBook", "WaterRipple1", "animatedRipple", {151, 217, 255}, "A circular blue water ripple expands and fades."},
	{"N044", "Shockwaves", "Shockwave", "FlipBook", "Shockwave2", "animatedShockwave", {134, 213, 255}, "A blue shockwave ring pulses outward and fades."},
	{"N045", "SwordSlashes", "Slash", "FlipBook", "Slash7", "animatedSlash", {215, 234, 255}, "A white sword slash sweeps across the view once."},
	{"N046", "WaterBubbles", "Water", "FlipBook", "Bubble1", "animatedBubble", {179, 232, 255}, "Pale blue bubbles rise and pop into flecks."},
	{"N047", "DebrisBurst", "Debris", "FlipBook", "Debris2", "animatedDebris", {220, 223, 227}, "Small stone fragments scatter outward and fall."},
}

local function sequence(points)
	local keys = {}
	for _, point in ipairs(points) do
		table.insert(keys, NumberSequenceKeypoint.new(point[1], point[2]))
	end
	return NumberSequence.new(keys)
end

local function color(rgb)
	return Color3.fromRGB(rgb[1], rgb[2], rgb[3])
end

local function setSize(emitter, a, b, c)
	emitter.Size = sequence({ {0, a}, {0.45, b}, {1, c} })
end

local function setFade(emitter, a, b)
	emitter.Transparency = sequence({ {0, a}, {0.6, b}, {1, 1} })
end

local function burst(emitter, count)
	emitter.Rate = 0
	emitter:SetAttribute("EmitCount", count)
end

local function continuous(emitter, rate)
	emitter.Rate = rate
	emitter:SetAttribute("EmitCount", 0)
end

local function configure(emitter, recipe)
	emitter.Enabled = true
	emitter.LightEmission = 0.4
	emitter.LightInfluence = 0
	emitter.Brightness = 0.7
	emitter.Orientation = Enum.ParticleOrientation.FacingCamera
	emitter.EmissionDirection = Enum.NormalId.Top
	emitter.SpreadAngle = Vector2.new(25, 25)
	emitter.Shape = Enum.ParticleEmitterShape.Sphere
	emitter.ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume
	emitter.ShapeInOut = Enum.ParticleEmitterShapeInOut.Outward
	emitter.ShapePartial = 1
	emitter.FlipbookLayout = Enum.ParticleFlipbookLayout.None
	emitter.FlipbookMode = Enum.ParticleFlipbookMode.OneShot
	emitter.FlipbookFramerate = NumberRange.new(1)
	emitter.Speed = NumberRange.new(0)
	emitter.Lifetime = NumberRange.new(1)
	emitter.Rotation = NumberRange.new(0)
	emitter.RotSpeed = NumberRange.new(0)
	emitter.Acceleration = Vector3.zero
	setSize(emitter, 1, 1, 0)
	setFade(emitter, 0.1, 0.3)

	if recipe == "flame" then
		continuous(emitter, 14)
		emitter.Lifetime = NumberRange.new(0.6, 1)
		emitter.Speed = NumberRange.new(3, 5)
		emitter.RotSpeed = NumberRange.new(-30, 30)
		setSize(emitter, 0.65, 1.25, 0)
		setFade(emitter, 0.15, 0.25)
	elseif recipe == "smoke" then
		continuous(emitter, 6)
		emitter.Lifetime = NumberRange.new(2.2, 3)
		emitter.Speed = NumberRange.new(1.1, 2)
		emitter.Drag = 1
		emitter.SpreadAngle = Vector2.new(30, 30)
		emitter.RotSpeed = NumberRange.new(-20, 20)
		emitter.LightEmission = 0
		emitter.LightInfluence = 0.4
		setSize(emitter, 1.2, 3, 4)
		setFade(emitter, 0.45, 0.55)
	elseif recipe == "cloud" then
		continuous(emitter, 2)
		emitter.Lifetime = NumberRange.new(3, 4)
		emitter.EmissionDirection = Enum.NormalId.Right
		emitter.Speed = NumberRange.new(0.8, 1.3)
		emitter.SpreadAngle = Vector2.new(8, 8)
		emitter.LightEmission = 0
		emitter.LightInfluence = 0.5
		setSize(emitter, 3, 4.5, 5)
		setFade(emitter, 0.4, 0.45)
	elseif recipe == "rock" then
		burst(emitter, 12)
		emitter.Lifetime = NumberRange.new(0.8, 1.3)
		emitter.Speed = NumberRange.new(10, 16)
		emitter.SpreadAngle = Vector2.new(180, 180)
		emitter.Acceleration = Vector3.new(0, -22, 0)
		emitter.Rotation = NumberRange.new(-180, 180)
		emitter.RotSpeed = NumberRange.new(-120, 120)
		emitter.LightEmission = 0
		setSize(emitter, 0.55, 0.7, 0)
		setFade(emitter, 0, 0.05)
	elseif recipe == "leaf" then
		continuous(emitter, 5)
		emitter.EmissionDirection = Enum.NormalId.Bottom
		emitter.Lifetime = NumberRange.new(2.5, 3.5)
		emitter.Speed = NumberRange.new(1.2, 2)
		emitter.SpreadAngle = Vector2.new(70, 70)
		emitter.Acceleration = Vector3.new(0, -1.5, 0)
		emitter.Rotation = NumberRange.new(-180, 180)
		emitter.RotSpeed = NumberRange.new(-90, 90)
		emitter.LightEmission = 0
		setSize(emitter, 0.5, 0.65, 0.45)
		setFade(emitter, 0, 0.05)
	elseif recipe == "dust" then
		burst(emitter, 10)
		emitter.Lifetime = NumberRange.new(0.8, 1.2)
		emitter.Speed = NumberRange.new(4, 7)
		emitter.Drag = 3
		emitter.SpreadAngle = Vector2.new(180, 180)
		emitter.LightEmission = 0
		setSize(emitter, 0.8, 2.1, 0)
		setFade(emitter, 0.3, 0.55)
	elseif recipe == "spark" then
		burst(emitter, 14)
		emitter.Lifetime = NumberRange.new(0.45, 0.65)
		emitter.Speed = NumberRange.new(8, 12)
		emitter.SpreadAngle = Vector2.new(180, 180)
		emitter.Acceleration = Vector3.new(0, -8, 0)
		emitter.LightEmission = 0.8
		emitter.Brightness = 1.1
		setSize(emitter, 0.45, 0.7, 0)
		setFade(emitter, 0.1, 0.15)
	elseif recipe == "ring" or recipe == "fireRing" then
		burst(emitter, 1)
		emitter.Lifetime = NumberRange.new(0.65)
		emitter.LightEmission = recipe == "fireRing" and 0.5 or 0.55
		emitter.Brightness = recipe == "fireRing" and 1 or 0.7
		setSize(emitter, 1.6, 4.8, 6.8)
		setFade(emitter, 0.1, 0.35)
	elseif recipe == "slash" then
		burst(emitter, 1)
		emitter.Lifetime = NumberRange.new(0.3)
		emitter.Rotation = NumberRange.new(-30)
		emitter.LightEmission = 0.65
		setSize(emitter, 3.2, 4, 4.3)
		setFade(emitter, 0.05, 0.25)
	elseif recipe == "impact" then
		burst(emitter, 1)
		emitter.Lifetime = NumberRange.new(0.25)
		emitter.LightEmission = 0.65
		emitter.Brightness = 1.2
		setSize(emitter, 3, 3.8, 0)
		setFade(emitter, 0.1, 0.25)
	elseif recipe == "snow" then
		continuous(emitter, 8)
		emitter.EmissionDirection = Enum.NormalId.Bottom
		emitter.Lifetime = NumberRange.new(2.5, 3.5)
		emitter.Speed = NumberRange.new(1.5, 2.5)
		emitter.SpreadAngle = Vector2.new(65, 65)
		emitter.Rotation = NumberRange.new(-180, 180)
		emitter.RotSpeed = NumberRange.new(-55, 55)
		emitter.LightEmission = 0.1
		setSize(emitter, 0.6, 0.8, 0.6)
		setFade(emitter, 0.1, 0.15)
	elseif recipe == "hearts" then
		continuous(emitter, 6)
		emitter.Lifetime = NumberRange.new(1.6, 2.3)
		emitter.Speed = NumberRange.new(1.4, 2.3)
		emitter.RotSpeed = NumberRange.new(-20, 20)
		setSize(emitter, 0.45, 0.75, 0)
		setFade(emitter, 0.1, 0.25)
	elseif recipe == "bubble" or recipe == "foam" then
		continuous(emitter, recipe == "bubble" and 5 or 3)
		emitter.Lifetime = NumberRange.new(2.2, 3)
		emitter.Speed = NumberRange.new(0.9, 1.6)
		emitter.Acceleration = Vector3.new(0, 0.6, 0)
		emitter.LightEmission = 0.1
		emitter.LightInfluence = 0.5
		setSize(emitter, recipe == "bubble" and 0.4 or 1.1, recipe == "bubble" and 0.7 or 1.7, 0)
		setFade(emitter, 0.25, 0.3)
	elseif recipe == "sigil" then
		burst(emitter, 1)
		emitter.Lifetime = NumberRange.new(2.5)
		emitter.RotSpeed = NumberRange.new(24)
		emitter.LightEmission = 0.65
		setSize(emitter, 3.5, 4.2, 4.4)
		setFade(emitter, 0.2, 0.1)
	elseif recipe == "toxic" then
		continuous(emitter, 3)
		emitter.Lifetime = NumberRange.new(1.5, 2)
		emitter.Speed = NumberRange.new(1, 2)
		emitter.Rotation = NumberRange.new(-60, 60)
		emitter.RotSpeed = NumberRange.new(-40, 40)
		emitter.LightEmission = 0.35
		setSize(emitter, 0.6, 1, 0)
		setFade(emitter, 0.1, 0.3)
	elseif recipe == "arcs" then
		continuous(emitter, 9)
		emitter.Lifetime = NumberRange.new(0.3, 0.45)
		emitter.Speed = NumberRange.new(2, 4)
		emitter.SpreadAngle = Vector2.new(180, 180)
		emitter.Rotation = NumberRange.new(-180, 180)
		emitter.LightEmission = 0.8
		setSize(emitter, 1.3, 2, 0)
		setFade(emitter, 0.1, 0.2)
	elseif recipe == "stars" then
		continuous(emitter, 10)
		emitter.Lifetime = NumberRange.new(0.7, 1.1)
		emitter.Speed = NumberRange.new(4, 6)
		emitter.SpreadAngle = Vector2.new(60, 60)
		emitter.LightEmission = 0.85
		emitter.Brightness = 1
		setSize(emitter, 0.5, 0.85, 0)
		setFade(emitter, 0.1, 0.1)
	end

	local flipbook = {
		animatedFire = { "Grid4x4", 20, 0.8, 8, 2.5, 1.2 },
		animatedSmoke = { "Grid4x4", 18, 0.9, 5, 1.5, 2.5 },
		animatedStrike = { "Grid4x4", 24, 0.67, 0, 0, 4.5 },
		animatedExplosion = { "Grid4x4", 20, 0.8, 0, 0, 5 },
		animatedBlood = { "Grid8x8", 64, 1, 0, 0, 3 },
		animatedRipple = { "Grid4x4", 20, 0.8, 0, 0, 5 },
		animatedShockwave = { "Grid4x4", 20, 0.8, 0, 0, 5 },
		animatedSlash = { "Grid4x4", 20, 0.8, 0, 0, 5 },
		animatedBubble = { "Grid4x4", 20, 0.8, 4, 1.3, 0.9 },
		animatedDebris = { "Grid4x4", 1, 0.9, 0, 8, 1.1 },
	}
	local spec = flipbook[recipe]
	if spec then
		emitter.FlipbookLayout = Enum.ParticleFlipbookLayout[spec[1]]
		emitter.FlipbookMode = Enum.ParticleFlipbookMode.OneShot
		emitter.FlipbookFramerate = NumberRange.new(spec[2])
		emitter.Lifetime = NumberRange.new(spec[3])
		emitter.Speed = NumberRange.new(spec[5] * 0.8, spec[5] * 1.2)
		setSize(emitter, spec[6] * 0.75, spec[6], spec[6] * 0.9)
		setFade(emitter, 0.05, 0.12)
		if spec[4] > 0 then continuous(emitter, spec[4]) else burst(emitter, recipe == "animatedDebris" and 8 or 1) end
		if recipe == "animatedFire" then
			emitter.EmissionDirection = Enum.NormalId.Top
			emitter.Brightness = 0.7
			emitter.LightEmission = 0.35
		elseif recipe == "animatedSmoke" then
			emitter.LightEmission = 0
			emitter.LightInfluence = 0.4
			emitter.Brightness = 0.55
			setSize(emitter, 1.1, 2.5, 3)
			setFade(emitter, 0.35, 0.45)
		elseif recipe == "animatedDebris" then
			emitter.SpreadAngle = Vector2.new(180, 180)
			emitter.Acceleration = Vector3.new(0, -14, 0)
			emitter.LightEmission = 0.35
			emitter.FlipbookStartRandom = true
			setSize(emitter, 0.55, 0.7, 0)
			setFade(emitter, 0.1, 0.15)
		elseif recipe == "animatedBubble" then
			emitter.LightEmission = 0
			emitter.LightInfluence = 0.5
			emitter.Brightness = 0.5
			setFade(emitter, 0.35, 0.45)
		else
			emitter.LightEmission = recipe == "animatedBlood" and 0.05 or 0.55
			emitter.Brightness = recipe == "animatedBlood" and 0.6 or 0.8
		end
	end
end

local function textureId(kind, name)
	local root = assert(PluginGuiService:FindFirstChild("CIX_Library"), "CIX Library is not loaded")
	local card = root.CIX_Library.Page[kind]:FindFirstChild(name)
	assert(card, "CIX card missing: " .. kind .. "/" .. name)
	local image = card:FindFirstChildWhichIsA("ImageButton", true)
	assert(image and image.Image ~= "", "CIX card has no image: " .. kind .. "/" .. name)
	return image.Image
end

local function promptGui(prompt)
	local gui = Instance.new("BillboardGui")
	gui.Name = "Prompt"
	gui.Size = UDim2.fromOffset(175, 76)
	gui.StudsOffset = Vector3.new(0, 8, 0)
	gui.MaxDistance = 40
	gui.LightInfluence = 0
	local text = Instance.new("TextLabel")
	text.Size = UDim2.fromScale(1, 1)
	text.BackgroundColor3 = Color3.fromRGB(15, 18, 25)
	text.BackgroundTransparency = 0.25
	text.TextColor3 = Color3.new(1, 1, 1)
	text.TextSize = 12
	text.TextWrapped = true
	text.Font = Enum.Font.GothamMedium
	text.Text = prompt
	text.Parent = gui
	return gui
end

function Pilot.build()
	local dataset = Workspace.Particles.Dataset
	local floors = Workspace.DatasetReviewFloors
	local made = 0
	for index, spec in ipairs(effects) do
		local id, familyName, category, kind, name, recipe, rgb, prompt = table.unpack(spec)
		local family = dataset:FindFirstChild(familyName)
		if not family then
			family = Instance.new("Folder")
			family.Name = familyName
			family.Parent = dataset
		end
		if not family:FindFirstChild(id .. "_V01_Base") then
			local column = (index - 1) % 6
			local row = math.floor((index - 1) / 6)
			local x, z = -100 + column * 40, -760 + row * 40
			local floor = Instance.new("Part")
			floor.Name = id .. "_CIXReview"
			floor.Anchored = true
			floor.Size = Vector3.new(24, 0.3, 24)
			floor.Position = Vector3.new(x, 80, z)
			floor.Color = Color3.fromRGB(41, 47, 58)
			floor.Material = Enum.Material.Slate
			floor.Parent = floors

			local attachment = Instance.new("Attachment")
			attachment.Name = id .. "_V01_Base"
			local height = 84
			if recipe == "leaf" or recipe == "snow" then height = 94 end
			if recipe == "cloud" then height = 90 end
			if recipe == "dust" or recipe == "animatedRipple" then height = 81.3 end
			attachment.CFrame = CFrame.new(x, height, z)
			attachment:SetAttribute("Category", category)
			attachment:SetAttribute("Split", "train")
			attachment.Parent = family

			local emitter = Instance.new("ParticleEmitter")
			emitter.Name = "ParticleEmitter"
			emitter.Texture = textureId(kind, name)
			emitter.Color = ColorSequence.new(color(rgb))
			configure(emitter, recipe)
			emitter.Parent = attachment
			promptGui(prompt).Parent = attachment
			made += 1
		end
	end
	return made
end

function Pilot.focus(id)
	for _, spec in ipairs(effects) do
		if spec[1] == id then
			local attachment = Workspace.Particles.Dataset[spec[2]][id .. "_V01_Base"]
			local emitter = attachment.ParticleEmitter
			local position = attachment.WorldPosition
			local camera = Workspace.CurrentCamera
			camera.CameraType = Enum.CameraType.Scriptable
			camera.CFrame = CFrame.lookAt(position + Vector3.new(0, 4, 17), position + Vector3.new(0, 2, 0))
			camera.FieldOfView = 50
			local count = emitter:GetAttribute("EmitCount")
			if count and count > 0 then emitter:Emit(count) end
			return attachment
		end
	end
	error("Unknown pilot ID: " .. tostring(id))
end

function Pilot.list()
	return effects
end

return Pilot
