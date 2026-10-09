--[[
	Tests for roblox/importer.lua

	How to run: in Studio (edit mode, ParticlesPlace.rbxl open), execute this file
	with the importer prepended, e.g. through the MCP execute_luau tool:

		local Importer = (function()
			<contents of roblox/importer.lua>
		end)()
		<contents of this file>

	The run returns a text summary ("PASS n  FAIL n" plus one line per failure).

	The tests never change the place: rebuilt instances are never parented into
	the game, executePlan is exercised against a detached Folder, and the last
	test checks that the dataset and the undo history are exactly as before.

	SAMPLES are real records taken from ParticlesPlace.rbxl:
	  1. SmokeRings/F021_V01_Base            burst      (EmitCount 1)
	  2. ElectricPulses/F049_V01_Base        continuous (EmitCount 0)
	  3. REVIEWPROMPTFORTESTING/FireAttachment  review entry, no PromptAlternates
]]

assert(Importer, "prepend roblox/importer.lua as `local Importer = (function() ... end)()`")

local HttpService = game:GetService("HttpService")
local History = game:GetService("ChangeHistoryService")
local DATASET = workspace.Particles.Dataset

local SAMPLES = [==[
{"attachment":{"attributes":{"Category":"Smoke","PromptAlternates":{"_type":"JSONString","value":["Show a smoke ring with a gray tint as it appears in a burst and fades.","Create a smoke ring with a gray tint that appears in a burst and fades."]},"Split":"train"},"class":"Attachment","name":"F021_V01_Base","properties":{"CFrame":{"_type":"CFrame","value":[118,3.6,-535,1,0,0,0,1,0,0,0,1]},"Visible":false}},"emitter":{"attributes":{"EmitCount":1},"class":"ParticleEmitter","name":"ParticleEmitter","properties":{"Acceleration":{"_type":"Vector3","value":[0,0,0]},"Brightness":5,"Color":{"_type":"ColorSequence","keypoints":[[0,0.698039,0.698039,0.698039],[1,0.698039,0.698039,0.698039]]},"Drag":1,"EmissionDirection":{"_type":"Enum","enum":"NormalId","value":"Top"},"Enabled":true,"FlipbookFramerate":{"_type":"NumberRange","value":[40,40]},"FlipbookLayout":{"_type":"Enum","enum":"ParticleFlipbookLayout","value":"Grid4x4"},"FlipbookMode":{"_type":"Enum","enum":"ParticleFlipbookMode","value":"OneShot"},"FlipbookStartRandom":false,"Lifetime":{"_type":"NumberRange","value":[1,1]},"LightEmission":1,"LightInfluence":0,"LockedToPart":false,"Orientation":{"_type":"Enum","enum":"ParticleOrientation","value":"FacingCamera"},"Rate":0,"RotSpeed":{"_type":"NumberRange","value":[0,0]},"Rotation":{"_type":"NumberRange","value":[-1000,1000]},"Shape":{"_type":"Enum","enum":"ParticleEmitterShape","value":"Box"},"ShapeInOut":{"_type":"Enum","enum":"ParticleEmitterShapeInOut","value":"Outward"},"ShapePartial":1,"ShapeStyle":{"_type":"Enum","enum":"ParticleEmitterShapeStyle","value":"Volume"},"Size":{"_type":"NumberSequence","keypoints":[[0,7,0],[1,7,0]]},"Speed":{"_type":"NumberRange","value":[0,0]},"SpreadAngle":{"_type":"Vector2","value":[-180,180]},"Squash":{"_type":"NumberSequence","keypoints":[[0,0,0],[1,0,0]]},"Texture":"http://www.roblox.com/asset/?id=14709268503","TimeScale":1,"Transparency":{"_type":"NumberSequence","keypoints":[[0,1,0],[0.25,0.12,0],[0.7,0.25,0],[1,1,0]]},"VelocityInheritance":0,"WindAffectsDrag":false,"ZOffset":0}},"formatVersion":1,"id":"SmokeRings/F021_V01_Base/ParticleEmitter","path":["SmokeRings","F021_V01_Base","ParticleEmitter"],"playback_mode":"burst","prompt":"Make a smoke ring with a gray tint that appears in a burst and fades.","prompt_gui":{"children":[{"class":"TextLabel","name":"TextLabel","properties":{"AnchorPoint":{"_type":"Vector2","value":[0,0]},"BackgroundColor3":{"_type":"Color3","value":[0.058824,0.082353,0.117647]},"BackgroundTransparency":0.25,"BorderSizePixel":0,"FontFace":{"_type":"Font","family":"rbxasset://fonts/families/GothamSSm.json","style":"Normal","weight":"Medium"},"Position":{"_type":"UDim2","value":[0,0,0,0]},"RichText":false,"Size":{"_type":"UDim2","value":[1,0,1,0]},"Text":"Make a smoke ring with a gray tint that appears in a burst and fades.","TextColor3":{"_type":"Color3","value":[1,1,1]},"TextScaled":false,"TextSize":12,"TextTransparency":0,"TextWrapped":true,"TextXAlignment":{"_type":"Enum","enum":"TextXAlignment","value":"Center"},"TextYAlignment":{"_type":"Enum","enum":"TextYAlignment","value":"Center"}}}],"class":"BillboardGui","name":"Prompt","properties":{"AlwaysOnTop":false,"Brightness":1,"ClipsDescendants":true,"Enabled":true,"ExtentsOffset":{"_type":"Vector3","value":[0,0,0]},"LightInfluence":0,"MaxDistance":100,"Size":{"_type":"UDim2","value":[0,175,0,76]},"SizeOffset":{"_type":"Vector2","value":[0,0]},"StudsOffset":{"_type":"Vector3","value":[0,10,0]},"StudsOffsetWorldSpace":{"_type":"Vector3","value":[0,0,0]},"ZIndexBehavior":{"_type":"Enum","enum":"ZIndexBehavior","value":"Sibling"}}}}
{"attachment":{"attributes":{"Category":"Electric","PromptAlternates":{"_type":"JSONString","value":["Create an electric pulse with a green tint that shimmers in place and fades.","Make an electric pulse with a green tint that shimmers in place and fades."]},"Split":"train"},"class":"Attachment","name":"F049_V01_Base","properties":{"CFrame":{"_type":"CFrame","value":[418,3.6,-325,1,0,0,0,1,0,0,0,1]},"Visible":false}},"emitter":{"attributes":{"EmitCount":0},"class":"ParticleEmitter","name":"ParticleEmitter","properties":{"Acceleration":{"_type":"Vector3","value":[0,0,0]},"Brightness":4,"Color":{"_type":"ColorSequence","keypoints":[[0,0.203922,1,0.431373],[1,0.203922,1,0.431373]]},"Drag":0,"EmissionDirection":{"_type":"Enum","enum":"NormalId","value":"Top"},"Enabled":true,"FlipbookFramerate":{"_type":"NumberRange","value":[1,1]},"FlipbookLayout":{"_type":"Enum","enum":"ParticleFlipbookLayout","value":"Grid4x4"},"FlipbookMode":{"_type":"Enum","enum":"ParticleFlipbookMode","value":"OneShot"},"FlipbookStartRandom":false,"Lifetime":{"_type":"NumberRange","value":[0.75,0.75]},"LightEmission":1,"LightInfluence":0,"LockedToPart":true,"Orientation":{"_type":"Enum","enum":"ParticleOrientation","value":"FacingCamera"},"Rate":20,"RotSpeed":{"_type":"NumberRange","value":[0,0]},"Rotation":{"_type":"NumberRange","value":[-360,360]},"Shape":{"_type":"Enum","enum":"ParticleEmitterShape","value":"Box"},"ShapeInOut":{"_type":"Enum","enum":"ParticleEmitterShapeInOut","value":"Outward"},"ShapePartial":1,"ShapeStyle":{"_type":"Enum","enum":"ParticleEmitterShapeStyle","value":"Volume"},"Size":{"_type":"NumberSequence","keypoints":[[0,4.44,0],[1,12,0]]},"Speed":{"_type":"NumberRange","value":[0.001,0.001]},"SpreadAngle":{"_type":"Vector2","value":[-180,180]},"Squash":{"_type":"NumberSequence","keypoints":[[0,0,0],[1,0,0]]},"Texture":"rbxassetid://11492870634","TimeScale":1,"Transparency":{"_type":"NumberSequence","keypoints":[[0,0.9875,0],[0.49764,0,0],[1,1,0]]},"VelocityInheritance":0,"WindAffectsDrag":false,"ZOffset":1.3}},"formatVersion":1,"id":"ElectricPulses/F049_V01_Base/ParticleEmitter","path":["ElectricPulses","F049_V01_Base","ParticleEmitter"],"playback_mode":"continuous","prompt":"Show an electric pulse with a green tint as it shimmers in place and fades.","prompt_gui":{"children":[{"class":"TextLabel","name":"TextLabel","properties":{"AnchorPoint":{"_type":"Vector2","value":[0,0]},"BackgroundColor3":{"_type":"Color3","value":[0.058824,0.082353,0.117647]},"BackgroundTransparency":0.25,"BorderSizePixel":0,"FontFace":{"_type":"Font","family":"rbxasset://fonts/families/GothamSSm.json","style":"Normal","weight":"Medium"},"Position":{"_type":"UDim2","value":[0,0,0,0]},"RichText":false,"Size":{"_type":"UDim2","value":[1,0,1,0]},"Text":"Show an electric pulse with a green tint as it shimmers in place and fades.","TextColor3":{"_type":"Color3","value":[1,1,1]},"TextScaled":false,"TextSize":12,"TextTransparency":0,"TextWrapped":true,"TextXAlignment":{"_type":"Enum","enum":"TextXAlignment","value":"Center"},"TextYAlignment":{"_type":"Enum","enum":"TextYAlignment","value":"Center"}}}],"class":"BillboardGui","name":"Prompt","properties":{"AlwaysOnTop":false,"Brightness":1,"ClipsDescendants":true,"Enabled":true,"ExtentsOffset":{"_type":"Vector3","value":[0,0,0]},"LightInfluence":0,"MaxDistance":100,"Size":{"_type":"UDim2","value":[0,175,0,76]},"SizeOffset":{"_type":"Vector2","value":[0,0]},"StudsOffset":{"_type":"Vector3","value":[0,10,0]},"StudsOffsetWorldSpace":{"_type":"Vector3","value":[0,0,0]},"ZIndexBehavior":{"_type":"Enum","enum":"ZIndexBehavior","value":"Sibling"}}}}
{"attachment":{"attributes":{"Category":"Misc","Split":"review"},"class":"Attachment","name":"FireAttachment","properties":{"CFrame":{"_type":"CFrame","value":[710,3.58015,618,1,0,0,0,1,0,0,0,1]},"Visible":false}},"emitter":{"attributes":{"EmitCount":0},"class":"ParticleEmitter","name":"ParticleEmitter","properties":{"Acceleration":{"_type":"Vector3","value":[0,5,0]},"Brightness":7,"Color":{"_type":"ColorSequence","keypoints":[[0,0.968627,0.484355,0.260155],[0.127807,0.968627,0.458744,0.240497],[0.238342,0.968627,0.262066,0.087606],[0.589965,0.968627,0.262066,0.087606],[0.731834,0,0,0],[1,0,0,0]]},"Drag":2,"EmissionDirection":{"_type":"Enum","enum":"NormalId","value":"Top"},"Enabled":true,"FlipbookFramerate":{"_type":"NumberRange","value":[1,1]},"FlipbookLayout":{"_type":"Enum","enum":"ParticleFlipbookLayout","value":"Grid4x4"},"FlipbookMode":{"_type":"Enum","enum":"ParticleFlipbookMode","value":"OneShot"},"FlipbookStartRandom":false,"Lifetime":{"_type":"NumberRange","value":[1.15,1.15]},"LightEmission":0.15,"LightInfluence":0.15,"LockedToPart":true,"Orientation":{"_type":"Enum","enum":"ParticleOrientation","value":"FacingCamera"},"Rate":35,"RotSpeed":{"_type":"NumberRange","value":[-70,70]},"Rotation":{"_type":"NumberRange","value":[-360,360]},"Shape":{"_type":"Enum","enum":"ParticleEmitterShape","value":"Box"},"ShapeInOut":{"_type":"Enum","enum":"ParticleEmitterShapeInOut","value":"Outward"},"ShapePartial":1,"ShapeStyle":{"_type":"Enum","enum":"ParticleEmitterShapeStyle","value":"Volume"},"Size":{"_type":"NumberSequence","keypoints":[[0,0,0],[0.1,0.233573,0],[0.2,0.457573,0],[0.3,0.683818,0],[0.4,0.919161,0],[0.5,1.169362,0],[0.6,1.440669,0],[0.7,1.741195,0],[0.8,2.083097,0],[0.9,2.487521,0],[1,3,0],[1,3,0]]},"Speed":{"_type":"NumberRange","value":[0.001,0.001]},"SpreadAngle":{"_type":"Vector2","value":[-20,20]},"Squash":{"_type":"NumberSequence","keypoints":[[0,0,0],[1,0,0]]},"Texture":"rbxassetid://13013256540","TimeScale":1,"Transparency":{"_type":"NumberSequence","keypoints":[[0,0.06875,0.0375],[0.539048,0.1375,0.04375],[0.779048,0.91875,0.014667],[0.87619,0.9875,0.010267],[1,1,0]]},"VelocityInheritance":0,"WindAffectsDrag":false,"ZOffset":0.4}},"formatVersion":1,"id":"REVIEWPROMPTFORTESTING/FireAttachment/ParticleEmitter","path":["REVIEWPROMPTFORTESTING","FireAttachment","ParticleEmitter"],"playback_mode":"continuous","prompt":"Create a small steady orange flame that blackens with an orange tint as it fades.","prompt_gui":{"children":[{"class":"TextLabel","name":"TextLabel","properties":{"AnchorPoint":{"_type":"Vector2","value":[0,0]},"BackgroundColor3":{"_type":"Color3","value":[0.058824,0.082353,0.117647]},"BackgroundTransparency":0.25,"BorderSizePixel":0,"FontFace":{"_type":"Font","family":"rbxasset://fonts/families/GothamSSm.json","style":"Normal","weight":"Medium"},"Position":{"_type":"UDim2","value":[0,0,0,0]},"RichText":false,"Size":{"_type":"UDim2","value":[1,0,1,0]},"Text":"Create a small steady orange flame that blackens with an orange tint as it fades.","TextColor3":{"_type":"Color3","value":[1,1,1]},"TextScaled":false,"TextSize":12,"TextTransparency":0,"TextWrapped":true,"TextXAlignment":{"_type":"Enum","enum":"TextXAlignment","value":"Center"},"TextYAlignment":{"_type":"Enum","enum":"TextYAlignment","value":"Center"}}}],"class":"BillboardGui","name":"Prompt","properties":{"AlwaysOnTop":false,"Brightness":1,"ClipsDescendants":true,"Enabled":true,"ExtentsOffset":{"_type":"Vector3","value":[0,0,0]},"LightInfluence":0,"MaxDistance":100,"Size":{"_type":"UDim2","value":[0,175,0,76]},"SizeOffset":{"_type":"Vector2","value":[0,0]},"StudsOffset":{"_type":"Vector3","value":[0,9,0]},"StudsOffsetWorldSpace":{"_type":"Vector3","value":[0,0,0]},"ZIndexBehavior":{"_type":"Enum","enum":"ZIndexBehavior","value":"Sibling"}}}}
]==]

--------------------------------------------------------------------------------
-- Tiny test runner
--------------------------------------------------------------------------------

local results = { pass = 0, fail = 0, failures = {} }
local cleanup = {}

local function track(instance)
	if instance then
		table.insert(cleanup, instance)
	end
	return instance
end

local function test(name, fn)
	local ok, err = pcall(fn)
	if ok then
		results.pass += 1
	else
		results.fail += 1
		table.insert(results.failures, "FAIL " .. name .. ": " .. tostring(err))
	end
end

local function check(condition, message)
	if not condition then
		error(message or "check failed", 2)
	end
end

local function eq(actual, expected, label)
	if actual ~= expected then
		error(string.format("%s: expected %s, got %s", label or "value", tostring(expected), tostring(actual)), 2)
	end
end

local function same(actual, expected, label)
	if not Importer.valuesEqual(actual, expected) then
		error(string.format("%s: expected %s, got %s", label or "value", tostring(expected), tostring(actual)), 2)
	end
end

local function anyMatch(list, pattern)
	for _, item in ipairs(list) do
		if string.find(item, pattern, 1, true) then
			return true
		end
	end
	return false
end

local function hasError(list, pattern)
	if not anyMatch(list, pattern) then
		error("no message containing \"" .. pattern .. "\" in: " .. table.concat(list, " || "), 2)
	end
end

-- Deep copy, so tests can modify records freely.
local function copy(value)
	if type(value) ~= "table" then
		return value
	end
	local out = {}
	for k, v in pairs(value) do
		out[k] = copy(v)
	end
	return out
end

local function decodeOk(raw)
	local value, err = Importer.decodeValue(raw)
	check(err == nil, "decode failed: " .. tostring(err))
	return value
end

local function decodeFails(raw, pattern)
	local value, err = Importer.decodeValue(raw)
	check(value == nil and err ~= nil, "expected decode to fail")
	if pattern then
		check(string.find(err, pattern, 1, true), "error \"" .. err .. "\" doesn't mention \"" .. pattern .. "\"")
	end
end

local function minimalRecord()
	return {
		formatVersion = 1,
		id = "Tests/T001_V01_Probe/ParticleEmitter",
		path = { "Tests", "T001_V01_Probe", "ParticleEmitter" },
		attachment = { class = "Attachment", name = "T001_V01_Probe" },
		emitter = {
			class = "ParticleEmitter",
			name = "ParticleEmitter",
			properties = { Rate = 5 },
			attributes = { EmitCount = 0 },
		},
	}
end

-- Snapshot of the dataset and the undo history, to prove the tests change nothing.
local function fingerprint()
	local parts = {}
	for _, d in ipairs(DATASET:GetDescendants()) do
		table.insert(parts, d:GetFullName() .. "|" .. d.ClassName)
		for name, value in pairs(d:GetAttributes()) do
			table.insert(parts, name .. "=" .. tostring(value))
		end
		if d:IsA("ParticleEmitter") then
			table.insert(parts, tostring(d.Rate) .. tostring(d.Color) .. tostring(d.Size) .. d.Texture)
		end
	end
	table.sort(parts)
	local canUndo, undoName = History:GetCanUndo()
	return table.concat(parts, "\n"), tostring(canUndo) .. ":" .. tostring(undoName), #workspace:GetChildren()
end

local beforeData, beforeUndo, beforeWorkspace = fingerprint()

local samples, sampleProblems = Importer.parseJsonl(SAMPLES)
local BURST, CONTINUOUS, REVIEW = samples[1], samples[2], samples[3]

local function liveAttachment(record)
	local instance = DATASET
	for i = 1, #record.path - 1 do
		instance = instance:FindFirstChild(record.path[i])
		assert(instance, "live instance missing for " .. record.id)
	end
	return instance
end

local function liveEmitter(record)
	return liveAttachment(record):FindFirstChild(record.path[#record.path])
end

--------------------------------------------------------------------------------
-- 1. Value decoding
--------------------------------------------------------------------------------

test("decode/plain values pass through", function()
	eq(decodeOk(3.5), 3.5)
	eq(decodeOk("rbxassetid://1"), "rbxassetid://1")
	eq(decodeOk(false), false)
end)

test("decode/Vector3 Vector2 Color3", function()
	same(decodeOk({ _type = "Vector3", value = { 1, -2, 3.5 } }), Vector3.new(1, -2, 3.5))
	same(decodeOk({ _type = "Vector2", value = { -180, 180 } }), Vector2.new(-180, 180))
	same(decodeOk({ _type = "Color3", value = { 0.1, 0.2, 0.3 } }), Color3.new(0.1, 0.2, 0.3))
end)

test("decode/UDim UDim2 Rect CFrame", function()
	same(decodeOk({ _type = "UDim", value = { 0.5, 10 } }), UDim.new(0.5, 10))
	same(decodeOk({ _type = "UDim2", value = { 0, 175, 0, 76 } }), UDim2.new(0, 175, 0, 76))
	same(decodeOk({ _type = "Rect", value = { 0, 0, 64, 32 } }), Rect.new(0, 0, 64, 32))
	local cf = CFrame.new(1, 2, 3) * CFrame.Angles(0.3, 0.2, 0.1)
	same(decodeOk({ _type = "CFrame", value = { cf:GetComponents() } }), cf)
end)

test("decode/NumberRange including negative ranges", function()
	same(decodeOk({ _type = "NumberRange", value = { -1000, 1000 } }), NumberRange.new(-1000, 1000))
	same(decodeOk({ _type = "NumberRange", value = { 2, 2 } }), NumberRange.new(2))
end)

test("decode/NumberSequence with and without envelopes", function()
	local plain = decodeOk({ _type = "NumberSequence", keypoints = { { 0, 1 }, { 1, 0 } } })
	same(plain, NumberSequence.new(1, 0))
	local withEnvelope = decodeOk({ _type = "NumberSequence", keypoints = { { 0, 2, 0.5 }, { 1, 2, 0.5 } } })
	eq(withEnvelope.Keypoints[1].Envelope, 0.5, "envelope")
end)

test("decode/NumberSequence with the 20-keypoint maximum", function()
	local list = {}
	for i = 0, 19 do
		table.insert(list, { i / 19, i })
	end
	eq(#decodeOk({ _type = "NumberSequence", keypoints = list }).Keypoints, 20, "keypoint count")
end)

test("decode/ColorSequence", function()
	local seq = decodeOk({ _type = "ColorSequence", keypoints = { { 0, 1, 0, 0 }, { 0.5, 0, 1, 0 }, { 1, 0, 0, 1 } } })
	eq(#seq.Keypoints, 3, "keypoint count")
	same(seq.Keypoints[2].Value, Color3.new(0, 1, 0), "middle color")
end)

test("decode/Enum BrickColor Font", function()
	eq(decodeOk({ _type = "Enum", enum = "ParticleEmitterShape", value = "Sphere" }), Enum.ParticleEmitterShape.Sphere)
	eq(decodeOk({ _type = "BrickColor", value = "Bright red" }), BrickColor.new("Bright red"))
	local font = decodeOk({ _type = "Font", family = "rbxasset://fonts/families/GothamSSm.json", weight = "Medium", style = "Normal" })
	eq(font.Weight, Enum.FontWeight.Medium, "font weight")
end)

test("decode/Content", function()
	if not Content then
		return -- not available in this Studio version
	end
	local content = decodeOk({ _type = "Content", uri = "rbxassetid://14709268503" })
	eq(typeof(content), "Content")
end)

test("decode/JSONString round-trips plain JSON", function()
	local text = decodeOk({ _type = "JSONString", value = { "a", "b" } })
	eq(typeof(text), "string")
	local back = HttpService:JSONDecode(text)
	eq(back[1], "a")
	eq(back[2], "b")
end)

test("decode/errors are reported, not thrown", function()
	decodeFails({ _type = "Vector3", value = { 1, 2 } }, "3 numbers")
	decodeFails({ _type = "Vector3", value = { 1, "x", 3 } }, "not a number")
	decodeFails({ _type = "NumberSequence", keypoints = { { 0, 1 } } }, "at least 2")
	decodeFails({ _type = "ColorSequence", keypoints = { { 0, 1, 1 }, { 1, 1, 1 } } }, "keypoint")
	decodeFails({ _type = "Enum", enum = "ParticleEmitterShape", value = "Hexagon" })
	decodeFails({ _type = "Mystery" }, "unknown _type")
	decodeFails({ 1, 2, 3 }, "untagged")
	decodeFails(nil)
end)

test("compare/tolerance and type checks", function()
	check(Importer.valuesEqual(0.1, 0.1 + 1e-7), "tiny float drift should be equal")
	check(not Importer.valuesEqual(0.1, 0.11), "real differences should not be equal")
	check(not Importer.valuesEqual(1, "1"), "different types should not be equal")
	check(
		Importer.valuesEqual(NumberSequence.new(0.698039), NumberSequence.new(0.6980392)),
		"float32 rounding in sequences should be equal"
	)
end)

--------------------------------------------------------------------------------
-- 2. Parsing
--------------------------------------------------------------------------------

test("parse/embedded samples load cleanly", function()
	eq(#samples, 3, "sample count")
	eq(#sampleProblems, 0, "sample problems")
end)

test("parse/blank lines, CRLF and bad lines", function()
	local text = '{"a":1}\r\n\r\n   \n{broken\n[1,2]\n{"b":2}'
	local records, problems = Importer.parseJsonl(text)
	eq(#records, 2, "records")
	eq(#problems, 2, "problems")
	eq(problems[1].line, 4, "first bad line number")
	eq(problems[2].line, 5, "second bad line number")
end)

test("parse/empty input", function()
	local records, problems = Importer.parseJsonl("")
	eq(#records, 0)
	eq(#problems, 0)
end)

--------------------------------------------------------------------------------
-- 3. Validation
--------------------------------------------------------------------------------

test("validate/samples are valid with no warnings", function()
	for _, record in ipairs(samples) do
		local ok, errors, warnings = Importer.validate(record)
		check(ok, record.id .. ": " .. table.concat(errors, " || "))
		eq(#warnings, 0, record.id .. " warnings")
	end
end)

test("validate/missing fields", function()
	local ok, errors = Importer.validate({ formatVersion = 1 })
	check(not ok)
	hasError(errors, "id")
	hasError(errors, "path")
	hasError(errors, "attachment: missing")
	hasError(errors, "emitter: missing")
	check(not Importer.validate("not a record"), "non-table record")
end)

test("validate/format versions", function()
	local newer = minimalRecord()
	newer.formatVersion = 99
	local ok, errors = Importer.validate(newer)
	check(not ok)
	hasError(errors, "newer than this importer")

	local missing = minimalRecord()
	missing.formatVersion = nil
	check(not Importer.validate(missing), "missing formatVersion")
end)

test("validate/migrations upgrade old records", function()
	local old = minimalRecord()
	old.formatVersion = 0
	old.emitter.properties = { OldRate = 5 }
	check(not Importer.validate(old), "no migration registered yet")

	Importer.migrations[0] = function(record)
		record.emitter.properties = { Rate = record.emitter.properties.OldRate }
		return record
	end
	local ok, errors = Importer.validate(copy(old))
	Importer.migrations[0] = nil
	check(ok, table.concat(errors, " || "))
end)

test("validate/unknown class, property, type and reserved names", function()
	local record = minimalRecord()
	record.attachment.class = "NotARealClass"
	record.emitter.properties = { Bogus = 1, Rate = "fast", Name = "x", Color = { _type = "Nope" } }
	local ok, errors = Importer.validate(record)
	check(not ok)
	hasError(errors, "unknown class")
	hasError(errors, "no property \"Bogus\"")
	hasError(errors, "expected number, got string")
	hasError(errors, "reserved")
	hasError(errors, "unknown _type")
end)

test("validate/attributes must be attribute-compatible", function()
	local record = minimalRecord()
	record.emitter.attributes = { Bad = { 1, 2 } }
	local ok, errors = Importer.validate(record)
	check(not ok)
	hasError(errors, "untagged")
end)

test("validate/path must match names", function()
	local record = minimalRecord()
	record.path = { "Tests", "Wrong", "Other" }
	local ok, errors = Importer.validate(record)
	check(not ok)
	hasError(errors, "emitter.name")
	hasError(errors, "attachment.name")
end)

test("validate/warnings never block", function()
	local record = copy(BURST)
	record.id = "something/else"
	record.playback_mode = "continuous"
	record.prompt = "a different prompt"
	record.some_future_field = { anything = true }
	local ok, errors, warnings = Importer.validate(record)
	check(ok, table.concat(errors, " || "))
	hasError(warnings, "id doesn't match")
	hasError(warnings, "playback_mode")
	hasError(warnings, "prompt doesn't match")
	eq(#warnings, 3, "warning count")
end)

--------------------------------------------------------------------------------
-- 4. Building against the real place
--------------------------------------------------------------------------------

for _, record in ipairs(samples) do
	test("deserialize/" .. record.id .. " matches the live emitter", function()
		local built, report = Importer.deserialize(record)
		track(built)
		check(built, "build failed: " .. table.concat(report.errors, " || "))
		eq(#report.errors, 0, "build errors")
		eq(built.Parent, nil, "built instance must not be parented")

		local live = liveEmitter(record)
		local rebuilt = built:FindFirstChild(live.Name)
		check(rebuilt, "rebuilt emitter missing")
		for name in pairs(record.emitter.properties) do
			same(rebuilt[name], live[name], name)
		end
		for name, value in pairs(live:GetAttributes()) do
			eq(rebuilt:GetAttribute(name), value, "attribute " .. name)
		end

		local liveAtt = liveAttachment(record)
		same(built.CFrame, liveAtt.CFrame, "attachment CFrame")
		for name, value in pairs(liveAtt:GetAttributes()) do
			if name == "PromptAlternates" then
				local a = HttpService:JSONDecode(built:GetAttribute(name))
				local b = HttpService:JSONDecode(value)
				eq(#a, #b, "PromptAlternates count")
				for i = 1, #b do
					eq(a[i], b[i], "PromptAlternates[" .. i .. "]")
				end
			else
				eq(built:GetAttribute(name), value, "attachment attribute " .. name)
			end
		end
		eq(built.Prompt.TextLabel.Text, liveAtt.Prompt.TextLabel.Text, "prompt text")

		eq(#Importer.apply(record, liveAtt).changes, 0, "diff against live")
		eq(#Importer.apply(record, built).changes, 0, "diff against rebuilt")
	end)
end

test("deserialize/review entry has no PromptAlternates", function()
	eq(REVIEW.attachment.attributes.PromptAlternates, nil)
	local built = track(Importer.deserialize(REVIEW))
	eq(built:GetAttribute("PromptAlternates"), nil)
end)

test("deserialize/default Prompt when only prompt text is given", function()
	local record = copy(CONTINUOUS)
	record.prompt_gui = nil
	record.prompt = "Fast blue sparks that fade quickly."
	local built = track(Importer.deserialize(record))
	check(built, "build failed")
	eq(built.Prompt.ClassName, "BillboardGui")
	eq(built.Prompt.TextLabel.Text, record.prompt)
end)

test("deserialize/no Prompt when there is no prompt at all", function()
	local built = track(Importer.deserialize(minimalRecord()))
	check(built, "build failed")
	eq(built:FindFirstChild("Prompt"), nil)
	eq(built.ParticleEmitter.Rate, 5)
end)

test("deserialize/invalid records build nothing", function()
	local record = minimalRecord()
	record.emitter.properties.Rate = "fast"
	local built, report = Importer.deserialize(record)
	eq(built, nil)
	hasError(report.errors, "expected number")
end)

test("deserialize/set failures and allowPartial", function()
	-- Passes validation (readable property, right type) but is read-only, so assigning it fails.
	local record = minimalRecord()
	record.attachment.children = {
		{ class = "Frame", name = "ReadOnly", properties = { AbsoluteSize = { _type = "Vector2", value = { 1, 1 } } } },
	}
	local built, report = Importer.deserialize(record)
	eq(built, nil, "strict build")
	check(#report.errors > 0, "expected a set error")

	local partial, partialReport = Importer.deserialize(record, { allowPartial = true })
	track(partial)
	check(partial, "partial build")
	check(#partialReport.errors > 0, "partial build still reports the error")
	eq(partial.ParticleEmitter.Rate, 5, "other properties still set")
end)

test("deserialize/multiple emitters and nested children", function()
	local record = minimalRecord()
	record.attachment.children = { { class = "Folder", name = "Extra", children = { { class = "Folder", name = "Deep" } } } }
	local built = track(Importer.deserialize(record))
	check(built and built.Extra.Deep, "nested children")
end)

test("deserialize/every attribute type", function()
	local record = minimalRecord()
	record.emitter.attributes = {
		EmitCount = 3,
		AString = "x",
		ABool = true,
		AVector3 = { _type = "Vector3", value = { 1, 2, 3 } },
		AVector2 = { _type = "Vector2", value = { 1, 2 } },
		AColor3 = { _type = "Color3", value = { 1, 0.5, 0 } },
		AUDim = { _type = "UDim", value = { 0.5, 4 } },
		AUDim2 = { _type = "UDim2", value = { 1, 0, 0.5, 10 } },
		ARect = { _type = "Rect", value = { 0, 0, 10, 10 } },
		ACFrame = { _type = "CFrame", value = { 1, 2, 3, 1, 0, 0, 0, 1, 0, 0, 0, 1 } },
		ARange = { _type = "NumberRange", value = { 1, 2 } },
		ANumSeq = { _type = "NumberSequence", keypoints = { { 0, 0 }, { 1, 1 } } },
		AColorSeq = { _type = "ColorSequence", keypoints = { { 0, 1, 1, 1 }, { 1, 0, 0, 0 } } },
		ABrick = { _type = "BrickColor", value = "Bright red" },
		AFont = { _type = "Font", family = "rbxasset://fonts/families/GothamSSm.json", weight = "Bold", style = "Italic" },
		AEnum = { _type = "Enum", enum = "Material", value = "Neon" },
		AJson = { _type = "JSONString", value = { k = "v" } },
	}
	local built, report = Importer.deserialize(record)
	track(built)
	check(built, table.concat(report.errors, " || "))
	local emitter = built.ParticleEmitter
	for name, raw in pairs(record.emitter.attributes) do
		local expected = decodeOk(raw)
		same(emitter:GetAttribute(name), expected, "attribute " .. name)
	end
	eq(#Importer.apply(record, built).changes, 0, "rebuilt matches its own record")
end)

--------------------------------------------------------------------------------
-- 5. apply()
--------------------------------------------------------------------------------

test("apply/dry run reports and changes nothing", function()
	local built = track(Importer.deserialize(BURST))
	local record = copy(BURST)
	record.emitter.properties.Rate = 42
	record.emitter.attributes.NewTag = "added"
	local result = Importer.apply(record, built)
	eq(#result.changes, 2, "change count")
	eq(result.committed, false)
	eq(built.ParticleEmitter.Rate, BURST.emitter.properties.Rate, "Rate untouched")
	eq(built.ParticleEmitter:GetAttribute("NewTag"), nil, "attribute untouched")
end)

test("apply/commit then repeat is a no-op", function()
	local built = track(Importer.deserialize(BURST))
	local record = copy(BURST)
	record.emitter.properties.Rate = 42
	record.emitter.attributes.NewTag = "added"
	local first = Importer.apply(record, built, { commit = true })
	eq(first.committed, true)
	eq(#first.errors, 0, "commit errors")
	eq(built.ParticleEmitter.Rate, 42)
	eq(built.ParticleEmitter:GetAttribute("NewTag"), "added")
	eq(#Importer.apply(record, built).changes, 0, "second pass")
end)

test("apply/missing children are created", function()
	local built = track(Importer.deserialize(BURST))
	built.Prompt:Destroy()
	local result = Importer.apply(BURST, built, { commit = true })
	eq(#result.changes, 1)
	eq(result.changes[1].kind, "create")
	eq(built.Prompt.TextLabel.Text, BURST.prompt)
end)

test("apply/never deletes; unlisted attributes are noted", function()
	local built = track(Importer.deserialize(BURST))
	built.ParticleEmitter:SetAttribute("LocalOnly", 1)
	local extra = Instance.new("Folder")
	extra.Name = "Extra"
	extra.Parent = built
	local result = Importer.apply(BURST, built, { commit = true })
	eq(#result.changes, 0)
	local noted = false
	for _, note in ipairs(result.notes) do
		noted = noted or (note.kind == "unlisted_attribute" and note.name == "LocalOnly")
	end
	check(noted, "LocalOnly should be noted")
	eq(built.ParticleEmitter:GetAttribute("LocalOnly"), 1, "attribute kept")
	check(built:FindFirstChild("Extra"), "extra child kept")
end)

test("apply/JSONString compares by meaning", function()
	local built = track(Importer.deserialize(BURST))
	local alternates = BURST.attachment.attributes.PromptAlternates.value
	local spaced = "[ " .. HttpService:JSONEncode(alternates[1]) .. " ,  " .. HttpService:JSONEncode(alternates[2]) .. " ]"
	built:SetAttribute("PromptAlternates", spaced)
	eq(#Importer.apply(BURST, built).changes, 0)
end)

test("apply/wrong target and invalid record", function()
	local built = track(Importer.deserialize(BURST))
	hasError(Importer.apply(CONTINUOUS, built).errors, "target is")
	local bad = copy(BURST)
	bad.formatVersion = 99
	hasError(Importer.apply(bad, built).errors, "newer")
end)

--------------------------------------------------------------------------------
-- 6. planImport / executePlan
--------------------------------------------------------------------------------

test("plan/samples are unchanged against the live dataset", function()
	local total = 0
	for _, d in ipairs(DATASET:GetDescendants()) do
		if d:IsA("ParticleEmitter") then
			total += 1
		end
	end
	local summary = Importer.summarize(Importer.planImport(samples, DATASET))
	eq(summary.unchanged, 3, "unchanged")
	eq(summary.create + summary.update, 0, "create + update")
	eq(summary.problems, 0, "problems")
	eq(summary.unlisted, total - 3, "unlisted")
end)

test("plan/new, invalid and duplicate records", function()
	local new = minimalRecord()
	local invalid = minimalRecord()
	invalid.id, invalid.path[2], invalid.attachment.name = "Tests/Bad/ParticleEmitter", "Bad", "Bad"
	invalid.emitter.properties.Rate = "fast"
	local plan = Importer.planImport({ new, copy(new), invalid, BURST }, DATASET)
	local summary = Importer.summarize(plan)
	eq(summary.create, 1, "create")
	eq(summary.unchanged, 1, "unchanged")
	eq(summary.problems, 2, "problems")
	local createAction
	for _, action in ipairs(plan.actions) do
		if action.kind == "create" then
			createAction = action
		end
	end
	eq(createAction.folders[1], "Tests", "folder path")
end)

test("plan/emitters sharing an attachment merge", function()
	local a = minimalRecord()
	local b = minimalRecord()
	b.emitter.name = "Sparks"
	b.path[3] = "Sparks"
	b.id = "Tests/T001_V01_Probe/Sparks"
	local plan = Importer.planImport({ a, b }, DATASET)
	eq(#plan.actions, 1, "one attachment")
	local names = {}
	for _, child in ipairs(plan.actions[1].tree.children) do
		names[child.name] = true
	end
	check(names.ParticleEmitter and names.Sparks, "both emitters in the tree")
end)

test("execute/imports into a detached root, then repeats as unchanged", function()
	local root = track(Instance.new("Folder"))
	local records = { copy(BURST), copy(CONTINUOUS), copy(REVIEW), minimalRecord() }
	local result = Importer.executePlan(Importer.planImport(records, root))
	eq(result.created, 4, "created")
	eq(#result.errors, 0, "errors")
	check(root.SmokeRings.F021_V01_Base.ParticleEmitter, "nested folders created")
	check(root.Tests.T001_V01_Probe.ParticleEmitter, "new family folder created")

	local again = Importer.summarize(Importer.planImport(records, root))
	eq(again.unchanged, 4, "second plan unchanged")
	eq(again.unlisted, 0, "nothing unlisted")

	local edited = copy(records)
	edited[2].emitter.properties.Rate = 99
	local update = Importer.executePlan(Importer.planImport(edited, root))
	eq(update.updated, 1, "updated")
	eq(root.ElectricPulses.F049_V01_Base.ParticleEmitter.Rate, 99)
end)

--------------------------------------------------------------------------------
-- 7. Playback
--------------------------------------------------------------------------------

test("playback/samples", function()
	eq(Importer.playbackMode(BURST), "burst")
	eq(Importer.emitCount(BURST), 1)
	eq(Importer.playbackMode(CONTINUOUS), "continuous")
	eq(Importer.playbackMode(liveEmitter(BURST)), "burst", "live burst emitter")
	eq(Importer.playbackMode(liveEmitter(CONTINUOUS)), "continuous", "live continuous emitter")
end)

test("playback/emit only fires bursts", function()
	local calls = {}
	local function fake(count)
		return {
			GetAttribute = function(_, name)
				return name == "EmitCount" and count or nil
			end,
			Emit = function(_, n)
				table.insert(calls, n)
			end,
		}
	end
	eq(Importer.emit(fake(7)), 7)
	eq(Importer.emit(fake(0)), 0)
	eq(Importer.emit(fake(nil)), 0)
	eq(#calls, 1, "Emit calls")
	eq(calls[1], 7)
end)

--------------------------------------------------------------------------------
-- 8. Nothing changed
--------------------------------------------------------------------------------

for _, instance in ipairs(cleanup) do
	instance:Destroy()
end

test("safety/place and undo history unchanged", function()
	local afterData, afterUndo, afterWorkspace = fingerprint()
	check(afterData == beforeData, "dataset changed")
	eq(afterUndo, beforeUndo, "undo history")
	eq(afterWorkspace, beforeWorkspace, "workspace child count")
end)

local summary = { string.format("PASS %d  FAIL %d", results.pass, results.fail) }
for _, line in ipairs(results.failures) do
	table.insert(summary, line)
end
return table.concat(summary, "\n")
