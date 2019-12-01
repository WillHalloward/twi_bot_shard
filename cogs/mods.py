from discord.ext import commands


def admin_or_me_check(ctx):
    if ctx.message.author.id == 268608466690506753:
        return True
    elif ctx.message.author.roles == 346842813687922689:
        return True
    else:
        return False


class ModCogs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(
        name="reset",
        brief="resets the cooldown of a command",
        help="resets the cooldown of a command",
        aliases=['removecooldown', 'cooldown'],
        usage='[Command]',
        hidden=False, )
    @commands.check(admin_or_me_check)
    async def reset(self, ctx, command):
        self.bot.get_command(command).reset_cooldown(ctx)


def setup(bot):
    bot.add_cog(ModCogs(bot))