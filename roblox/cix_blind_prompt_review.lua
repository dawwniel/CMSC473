-- Step through reserved CIX effects without showing their saved prompt labels.

local ServerStorage = game:GetService("ServerStorage")
local expansion = require(ServerStorage.Prompt2Particles.CIXExpansion)

local Review = {}
local ids = {
	"N156", "N318", "N319", "N060", "N061", "N062",
	"N238", "N239", "N240", "N130", "N131", "N132",
	"N146", "N147", "N148", "N153", "N438", "N445",
	"N226", "N547", "N591", "N352", "N353", "N426",
}
local families = {}
for _, spec in expansion.list() do
	families[spec.id] = spec.family
end

local index = 0
local previous = nil

local function restorePrevious()
	if previous and previous.Parent then
		local gui = previous:FindFirstChild("Prompt")
		if gui then gui.Enabled = true end
	end
	previous = nil
end

function Review.next()
	restorePrevious()
	index += 1
	local id = ids[index]
	if not id then
		print("Blind prompt review complete: " .. #ids .. " effects")
		return nil
	end
	local family = assert(families[id], "unknown CIX effect: " .. id)
	local attachment = workspace.Particles.Dataset[family][id .. "_V01_Base"]
	attachment.Prompt.Enabled = false
	previous = attachment
	expansion.focus(id)
	print(string.format("Blind prompt %d/%d: %s", index, #ids, id))
	return id
end

function Review.reset()
	restorePrevious()
	index = 0
	print("Blind prompt review reset")
end

return Review
